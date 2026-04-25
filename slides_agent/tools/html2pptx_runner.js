#!/usr/bin/env node
/**
 * dom-to-pptx-based HTML → PPTX runner.
 *
 * Strategy:
 *   1. Read each slide HTML file, extract its <head> assets and body content.
 *   2. Build a temporary "orchestrator" HTML file in the SAME directory as the
 *      slides so that relative paths (./assets/, ./_theme.css) resolve correctly.
 *   3. Open the orchestrator in a headless Chromium page via Playwright.
 *   4. Inject the dom-to-pptx self-contained browser bundle.
 *   5. Call exportToPptx() on all .slide-host divs — each becomes one PPTX slide.
 *      dom-to-pptx uses window.getComputedStyle + getBoundingClientRect so every
 *      CSS effect (gradients, SVGs, custom fonts, shadows) is faithfully converted
 *      to native editable PPTX shapes and text boxes.
 *   6. Intercept the browser download and write the PPTX to outputPath.
 *   7. Delete the orchestrator file.
 *
 * Usage:
 *   node html2pptx_runner.js \
 *     --output out.pptx \
 *     --layout LAYOUT_16x9_1280 \
 *     [--tmp-dir /tmp] \
 *     -- slide1.html slide2.html ...
 *
 *   (--html2pptx accepted for backwards compat but unused)
 */

'use strict';

// Isolate Node.js Playwright browsers from Python Playwright to prevent
// npm's cleanup from deleting Python's browser binaries.
const path   = require('path');
if (!process.env.PLAYWRIGHT_BROWSERS_PATH) {
  // Prefer a project-local cache in the current working directory.
  // (The launcher creates/runs projects from ./openswarm, so this becomes ./openswarm/.playwright-browsers.)
  process.env.PLAYWRIGHT_BROWSERS_PATH = path.resolve(process.cwd(), '.playwright-browsers');
}
const fs     = require('fs');
const os     = require('os');
const crypto = require('crypto');
const https  = require('https');
const http   = require('http');

// Layout → PPTX dimensions (inches) + expected HTML viewport (px)
const LAYOUTS = {
    'LAYOUT_16x9_1280': { name: 'LAYOUT_16x9_1280', width: 13.333, height:  7.5,   viewportW: 1280, viewportH:  720 },
    'LAYOUT_16x9_1920': { name: 'LAYOUT_16x9_1920', width: 20.0,   height: 11.25,  viewportW: 1920, viewportH: 1080 },
    'LAYOUT_16x9':      { name: 'LAYOUT_16x9',      width: 10.0,   height:  5.625, viewportW:  960, viewportH:  540 },
    'LAYOUT_4x3':       { name: 'LAYOUT_4x3',       width: 10.0,   height:  7.5,   viewportW:  960, viewportH:  720 },
    'LAYOUT_16x10':     { name: 'LAYOUT_16x10',     width: 10.0,   height:  6.25,  viewportW:  960, viewportH:  625 },
};

// Extra wait after page load so CDN fonts, Tailwind, etc. fully apply.
const SETTLE_MS = 2000;

// Timeout for the full export (all slides).
const EXPORT_TIMEOUT_MS = 180_000;

// ─── CSS scoping ──────────────────────────────────────────────────────────────

/**
 * Transform an inline <style> block from a slide so it is safe inside the
 * orchestrator page that hosts multiple slides as sibling divs.
 *
 * Single-pass block-level parser — each CSS rule is handled exactly once:
 *
 *  • html / body rules   → selector replaced with ".slide-host:nth-child(N)"
 *                           Background-color/font etc. are preserved.
 *                           Width/height/overflow conflicts are harmless because
 *                           the .slide-host inline style has higher specificity.
 *
 *  • @-rules             → kept verbatim (@keyframes, @font-face, @media …)
 *
 *  • everything else     → prefixed with ".slide-host:nth-child(N)" to prevent
 *                           cross-slide class-name bleed.
 */
function scopeSelector(selector, scope) {
    if (!selector) return selector;
    if (/^:root\b/i.test(selector)) return selector.replace(/^:root\b/i, scope);
    if (/^(html|body)\b/i.test(selector)) return selector.replace(/^(html|body)\b/i, scope);
    return `${scope} ${selector}`;
}

function scopeSlideStyle(css, slideIndex) {
    const scope = `.slide-host:nth-child(${slideIndex + 1})`;
    let result = '';
    let i = 0;

    while (i < css.length) {
        const braceOpen = css.indexOf('{', i);
        if (braceOpen === -1) { result += css.slice(i); break; }

        const selectorText = css.slice(i, braceOpen);
        const trimmed      = selectorText.trim();

        // Walk to the matching closing brace (handles one level of nesting)
        let depth = 1, j = braceOpen + 1;
        while (j < css.length && depth > 0) {
            if (css[j] === '{') depth++;
            else if (css[j] === '}') depth--;
            j++;
        }
        const block = css.slice(braceOpen, j); // "{ … }"

        if (!trimmed) {
            result += selectorText + block;
        } else if (trimmed.startsWith('@')) {
            // @-rules: keep verbatim — don't scope keyframes, font-face, etc.
            result += selectorText + block;
        } else {
            const selectors = trimmed.split(',').map(s => s.trim()).filter(Boolean);
            const scoped = selectors.map(s => scopeSelector(s, scope)).join(', ');
            result += `${scoped} ${block}\n`;
        }

        i = j;
    }

    return result;
}

// ─── HTML parsing helpers ─────────────────────────────────────────────────────

/**
 * Convert CSS ::before / ::after pseudo-element rules that carry tiling
 * background patterns (background-image + background-size) into real <div>
 * nodes injected as the first child of the matching element.
 *
 * dom-to-pptx iterates actual DOM nodes and cannot see pseudo-elements, so
 * without this step any grid/dot pattern defined via ::before is invisible in
 * the exported PPTX.
 *
 * Also strips those background properties from the pseudo-element rule so the
 * browser does not double-render the pattern.
 */
function materializePseudoBackgrounds(html) {
    // Collect all <style> block contents
    const styleBlocks = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)].map(m => m[1]);
    const styleContent = styleBlocks.join('\n');

    const pseudoInjections = []; // { className, divStyle }

    // Match every selector::before / ::after rule
    const ruleRe = /([\w\s.#:-]+?)\s*::(?:before|after)\s*\{/g;
    let rm;
    while ((rm = ruleRe.exec(styleContent)) !== null) {
        const selectorRaw = rm[1].trim();
        const blockStart  = rm.index + rm[0].length;

        // Find the matching closing brace (depth-aware)
        let depth = 1, pos = blockStart;
        while (pos < styleContent.length && depth > 0) {
            if      (styleContent[pos] === '{') depth++;
            else if (styleContent[pos] === '}') depth--;
            pos++;
        }
        const ruleBody = styleContent.slice(blockStart, pos - 1);

        if (!/background-image\s*:/i.test(ruleBody) || !/background-size\s*:/i.test(ruleBody)) continue;

        // Extract background-image with paren-aware scan so gradient commas
        // don't prematurely terminate the value
        const bgImageKeyStart = ruleBody.search(/background-image\s*:/i);
        if (bgImageKeyStart < 0) continue;
        let bgImageValue = '';
        let valStart = ruleBody.indexOf(':', bgImageKeyStart) + 1;
        let d = 0;
        for (let vi = valStart; vi < ruleBody.length; vi++) {
            const ch = ruleBody[vi];
            if      (ch === '(') d++;
            else if (ch === ')') d--;
            else if (ch === ';' && d === 0) break;
            bgImageValue += ch;
        }
        bgImageValue = bgImageValue.trim().replace(/\s+/g, ' ');

        const bgSizeM  = ruleBody.match(/background-size\s*:\s*([^;]+)/i);
        if (!bgSizeM) continue;
        const bgSize   = bgSizeM[1].trim();

        const zIndexM  = ruleBody.match(/z-index\s*:\s*([^;]+)/i);
        const zIndex   = zIndexM ? zIndexM[1].trim() : '0';

        const divStyle = `position:absolute;inset:0;background-image:${bgImageValue};` +
                         `background-size:${bgSize};z-index:${zIndex};pointer-events:none;`;

        // Extract every class name from the selector (.slide-root, .bg-grid, …)
        for (const [, cls] of selectorRaw.matchAll(/\.([\w-]+)/g)) {
            pseudoInjections.push({ className: cls, divStyle });
        }
    }

    if (pseudoInjections.length === 0) return html;

    let result = html;

    // 1. Neutralize the ::before/::after background in the <style> blocks so
    //    the browser doesn't double-render the pattern on top of our real div.
    result = result.replace(/<style([^>]*)>([\s\S]*?)<\/style>/gi, (_, attrs, css) => {
        const cleaned = css.replace(
            /([\w\s.#:-]+?)\s*::(?:before|after)\s*\{([^}]*)\}/g,
            (full, sel, body) => {
                if (!/background-image\s*:/i.test(body) || !/background-size\s*:/i.test(body)) return full;
                const neutralized = body
                    .replace(/background-image\s*:[^;]+;?/gi, 'background-image:none;')
                    .replace(/background-size\s*:[^;]+;?/gi, '');
                return `${sel}::before{${neutralized}}`;
            }
        );
        return `<style${attrs}>${cleaned}</style>`;
    });

    // 2. Inject a real <div> as the first child of each matched element
    for (const { className, divStyle } of pseudoInjections) {
        const injectedDiv = `<div style="${divStyle}"></div>`;
        const escapedCls  = className.replace(/[-]/g, '\\-');
        // Match any block-level opening tag that carries the target class
        const tagRe = new RegExp(
            `(<(?:div|section|main|article|aside|header|footer|span|a)[^>]*class="[^"]*\\b${escapedCls}\\b[^"]*"[^>]*>)`,
            'g'
        );
        result = result.replace(tagRe, `$1${injectedDiv}`);
    }

    return result;
}

function parseSlideHtml(html) {
    const headMatch = html.match(/<head[^>]*>([\s\S]*?)<\/head>/i);
    const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    return {
        head: headMatch ? headMatch[1] : '',
        body: bodyMatch ? bodyMatch[1] : html,
    };
}

function isRemoteHref(href) {
    return /^https?:\/\//i.test(href) || href.startsWith('//') || href.startsWith('data:');
}

function resolveStylesheetPath(href, slideDir) {
    const cleanHref = href.split('#')[0].split('?')[0];
    if (!cleanHref) return null;

    if (cleanHref.startsWith('file://')) {
        let filePath = cleanHref.replace(/^file:\/\//i, '');
        if (/^\/[A-Za-z]:/.test(filePath)) filePath = filePath.slice(1);
        return filePath.replace(/\//g, path.sep);
    }

    if (path.isAbsolute(cleanHref)) return cleanHref;
    return path.resolve(slideDir, cleanHref);
}

function patchDomToPptxBundle(bundleCode, layoutName, layout) {
    const layoutString = JSON.stringify(layoutName);
    const defineLayoutCode = [
        `pptx.defineLayout({ name: ${layoutString}, width: ${layout.width}, height: ${layout.height} });`,
        `pptx.layout = ${layoutString};`,
    ].join(' ');

    let patchedCode = bundleCode;
    let patchedLayoutName = false;
    let patchedLayoutSize = false;

    patchedCode = patchedCode.replace(
        /pptx\.layout\s*=\s*'LAYOUT_16x9';/,
        () => {
            patchedLayoutName = true;
            return defineLayoutCode;
        }
    );

    patchedCode = patchedCode.replace(
        /const PPTX_WIDTH_IN\s*=\s*10;\s*const PPTX_HEIGHT_IN\s*=\s*5\.625;/,
        () => {
            patchedLayoutSize = true;
            return `const PPTX_WIDTH_IN = ${layout.width};\n        const PPTX_HEIGHT_IN = ${layout.height};`;
        }
    );

    if (!patchedLayoutName || !patchedLayoutSize) {
        throw new Error('Failed to patch dom-to-pptx bundle for custom layout handling.');
    }

    return patchedCode;
}

/**
 * Extract <link> tags (deduplicated by href) and <style> blocks (scoped to the
 * slide's nth-child position) from a slide's <head> string.
 */
function extractHeadAssets(headHtml, seenLinks, slideIndex, slideDir) {
    const assets = [];

    // <link> tags — local stylesheets are inlined + scoped, remote assets stay links
    for (const m of headHtml.matchAll(/<link\b[^>]*>/gi)) {
        const tag = m[0];
        const relMatch = tag.match(/rel\s*=\s*["']([^"']+)["']/i);
        const rel = relMatch ? relMatch[1].toLowerCase() : '';
        const hrefMatch = tag.match(/href\s*=\s*["']([^"']+)["']/i);
        const href = hrefMatch ? hrefMatch[1] : tag;

        if (hrefMatch && rel.includes('stylesheet') && !isRemoteHref(href)) {
            const stylesheetPath = resolveStylesheetPath(href, slideDir);
            if (stylesheetPath && fs.existsSync(stylesheetPath)) {
                const rawCss = fs.readFileSync(stylesheetPath, 'utf8');
                const scopedCss = scopeSlideStyle(rawCss, slideIndex);
                assets.push(`<style>${scopedCss}</style>`);
                continue;
            }
        }

        if (!seenLinks.has(href)) {
            seenLinks.add(href);
            const patched = href.includes('fonts.googleapis.com') && !tag.includes('crossorigin')
                ? tag.replace('>', ' crossorigin="anonymous">')
                : tag;
            assets.push(patched);
        }
    }

    // <style> blocks — scoped per slide to prevent cross-slide bleed
    for (const m of headHtml.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)) {
        const rawCss    = m[1];
        const scopedCss = scopeSlideStyle(rawCss, slideIndex);
        assets.push(`<style>${scopedCss}</style>`);
    }

    return assets;
}

// ─── Orchestrator builder ─────────────────────────────────────────────────────

function buildOrchestratorHtml(slides, layout, domToPptxBundlePath) {
    const seenLinks    = new Set();
    const allAssets    = [];
    const slideHostDivs = [];

    slides.forEach(({ head, body, dir }, idx) => {
        for (const asset of extractHeadAssets(head, seenLinks, idx, dir)) {
            allAssets.push(asset);
        }
        slideHostDivs.push(
            `<div class="slide-host" style="` +
            `width:${layout.viewportW}px;height:${layout.viewportH}px;` +
            `position:relative;overflow:hidden;flex-shrink:0;">` +
            body +
            `</div>`
        );
    });

    const bundleCode = patchDomToPptxBundle(
        fs.readFileSync(domToPptxBundlePath, 'utf8'),
        layout.name,
        layout
    );

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  ${allAssets.join('\n  ')}
  <style>
    * { box-sizing: border-box; }
    /* Orchestrator resets — must NOT set overflow:hidden or fixed height on body */
    html { margin: 0; padding: 0; background: #1a1a1a; }
    body { margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0; }
    /* The .slide div often carries a redundant background identical to .slide-wrapper / .slide-host.
       When .slide has z-index > 0 (stacking context), dom-to-pptx places its background shape
       on top of decorative siblings (orbs, grid-lines) that have lower z-indices, making those
       elements invisible. The background is already provided by .slide-host and .slide-wrapper,
       so making .slide transparent here restores the correct layering in the exported PPTX. */
    .slide-host .slide { background: transparent !important; }
  </style>
</head>
<body>
  ${slideHostDivs.join('\n  ')}
  <script>${bundleCode}</script>
</body>
</html>`;
}

// ─── File URL helper ──────────────────────────────────────────────────────────

function toFileUrl(absPath) {
    let p = path.resolve(absPath).replace(/\\/g, '/');
    if (!p.startsWith('/')) p = '/' + p;
    return `file://${p}`;
}

// ─── Font Awesome materialization ────────────────────────────────────────────

/**
 * Maps Font Awesome style-prefix classes to the font-family and font-weight
 * that PowerPoint must use to render the glyph correctly.
 */
const FA_STYLE_MAP = {
    // FA 6 long-form
    'fa-solid':   { family: 'Font Awesome 6 Free',   weight: 900 },
    'fa-regular': { family: 'Font Awesome 6 Free',   weight: 400 },
    'fa-light':   { family: 'Font Awesome 6 Free',   weight: 300 },
    'fa-thin':    { family: 'Font Awesome 6 Free',   weight: 100 },
    'fa-brands':  { family: 'Font Awesome 6 Brands', weight: 400 },
    // FA 6 / FA 5 short-form
    'fas': { family: 'Font Awesome 6 Free',   weight: 900 },
    'far': { family: 'Font Awesome 6 Free',   weight: 400 },
    'fal': { family: 'Font Awesome 6 Free',   weight: 300 },
    'fat': { family: 'Font Awesome 6 Free',   weight: 100 },
    'fab': { family: 'Font Awesome 6 Brands', weight: 400 },
    // FA 5 fallback (free tier only had solid + brands)
    'fa':  { family: 'Font Awesome 5 Free',   weight: 900 },
};

/** Return FA CSS hrefs found in any slide <head>. */
function collectFontAwesomeHrefs(slides) {
    const FA_PATTERNS = ['fontawesome', 'font-awesome', 'fortawesome'];
    const seen = new Set();
    for (const { head } of slides) {
        for (const m of head.matchAll(/<link\b[^>]*>/gi)) {
            const hrefMatch = m[0].match(/href\s*=\s*["']([^"']+)["']/i);
            if (!hrefMatch) continue;
            const href = hrefMatch[1];
            if (FA_PATTERNS.some(p => href.toLowerCase().includes(p)) && !seen.has(href)) {
                seen.add(href);
            }
        }
    }
    return [...seen];
}

/**
 * Parse Font Awesome CSS and return a map of icon class → Unicode character.
 * Handles both minified and pretty-printed CSS, and both :before / ::before.
 */
function parseFontAwesomeIconMap(cssText) {
    const iconMap = {};
    const re = /\.fa-([\w-]+)::?before\s*\{[^}]*content:\s*["']\\([0-9a-fA-F]+)["']/g;
    let m;
    while ((m = re.exec(cssText)) !== null) {
        iconMap[`fa-${m[1]}`] = String.fromCodePoint(parseInt(m[2], 16));
    }
    return iconMap;
}

/**
 * Download Font Awesome TTF font files and build the icon map.
 * Returns { fonts: [{name, url}], iconMap: {className: unicodeChar} }.
 *
 * Font Awesome uses CSS ::before pseudo-elements for icons, which dom-to-pptx
 * cannot see. We parse the icon map here so materializeFontAwesomeIcons() can
 * replace <i> elements with real <span> nodes containing the glyph character.
 */
async function downloadFontAwesomeFonts(faHrefs) {
    if (!faHrefs.length) return { fonts: [], iconMap: {} };

    const fonts    = [];
    const iconMap  = {};
    const seenUrls = new Set();

    for (const href of faHrefs) {
        let css;
        try {
            css = (await fetchBuf(href)).toString('utf8');
        } catch (e) {
            console.warn(`[fa] Could not fetch ${href}:`, e.message);
            continue;
        }

        Object.assign(iconMap, parseFontAwesomeIconMap(css));

        // Resolve relative font URLs against the CSS file's base URL.
        const baseUrl = href.substring(0, href.lastIndexOf('/') + 1);

        const faceRe = /@font-face\s*\{([\s\S]*?)\}/g;
        let fm;
        while ((fm = faceRe.exec(css)) !== null) {
            const block     = fm[1];
            const nameMatch = block.match(/font-family\s*:\s*['"]([^'"]+)['"]/);
            if (!nameMatch) continue;

            // Prefer TTF — the format PowerPoint can embed.
            const ttfMatch = block.match(/url\(['"]?([^'")\s]+\.ttf)['"]?\)/i);
            if (!ttfMatch) continue;

            const rawUrl  = ttfMatch[1];
            const fontUrl = rawUrl.startsWith('http') ? rawUrl : new URL(rawUrl, baseUrl).href;
            if (seenUrls.has(fontUrl)) continue;
            seenUrls.add(fontUrl);

            try {
                const buf  = await fetchBuf(fontUrl);
                const name = nameMatch[1].trim();
                fonts.push({ name, url: `data:font/ttf;base64,${buf.toString('base64')}` });
                console.log(`[fa] "${name}" (${fontUrl.split('/').pop()}) — ${Math.round(buf.length / 1024)} KB`);
            } catch (e) {
                console.warn(`[fa] Could not download font:`, e.message);
            }
        }
    }

    console.log(`[fa] ${fonts.length} font file(s), ${Object.keys(iconMap).length} icons mapped`);
    return { fonts, iconMap };
}

/**
 * Replace Font Awesome <i> elements with real <span> nodes containing the
 * Unicode glyph character so dom-to-pptx can see and embed them.
 *
 * dom-to-pptx traverses actual DOM nodes; it cannot read CSS ::before
 * pseudo-element content. Without this step, FA icons would be invisible in
 * the exported PPTX even if the font file is embedded.
 */
function materializeFontAwesomeIcons(html, iconMap) {
    if (!Object.keys(iconMap).length) return html;

    return html.replace(/<i\b[^>]*class=["']([^"']*)["'][^>]*>\s*<\/i>/gi, (match, classList) => {
        const classes = classList.trim().split(/\s+/);

        // Determine font-family + weight from the style-prefix class.
        let styleInfo = null;
        for (const cls of classes) {
            if (FA_STYLE_MAP[cls]) { styleInfo = FA_STYLE_MAP[cls]; break; }
        }
        if (!styleInfo) return match;

        // Find the icon class (e.g. fa-star) — starts with fa- but is not a prefix.
        const iconClass = classes.find(c => c.startsWith('fa-') && !FA_STYLE_MAP[c]);
        if (!iconClass || !iconMap[iconClass]) return match;

        const { family, weight } = styleInfo;
        const glyph = iconMap[iconClass];
        return `<span style="font-family:'${family}';font-weight:${weight};font-style:normal;">${glyph}</span>`;
    });
}

// ─── Font pre-download (bypass CORS) ─────────────────────────────────────────

/**
 * Fetch a URL as a Buffer, following redirects.
 * The minimal User-Agent causes Google Fonts to return TTF instead of WOFF2
 * or EOT — TTF is the format PowerPoint can embed; WOFF2/EOT are browser-only.
 */
function fetchBuf(url, ua = 'Mozilla/5.0') {
    return new Promise((resolve, reject) => {
        const mod = url.startsWith('https:') ? https : http;
        mod.get(url, { headers: { 'User-Agent': ua } }, res => {
            if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
                return fetchBuf(res.headers.location, ua).then(resolve, reject);
            }
            if (res.statusCode < 200 || res.statusCode >= 400) {
                res.resume();
                return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
            }
            const chunks = [];
            res.on('data', c => chunks.push(c));
            res.on('end', () => resolve(Buffer.concat(chunks)));
            res.on('error', reject);
        }).on('error', reject);
    });
}

/** Collect unique Google Fonts hrefs from all slide <head> sections. */
function collectGoogleFontsHrefs(slides) {
    const seen = new Set();
    for (const { head } of slides) {
        for (const m of head.matchAll(/<link\b[^>]*>/gi)) {
            const hrefMatch = m[0].match(/href\s*=\s*["']([^"']+)["']/i);
            if (!hrefMatch) continue;
            const href = hrefMatch[1];
            if (href.includes('fonts.googleapis.com') && !seen.has(href)) seen.add(href);
        }
    }
    return [...seen];
}

/**
 * Pre-download Google Fonts as TTF and return data: URI descriptors for
 * dom-to-pptx's `fonts` option. One descriptor per unique font-family name
 * (the first/lightest weight encountered, which serves as the "regular" face).
 *
 * Using a data: URI means the browser page can fetch() it without CORS issues.
 * The `type` will default to 'ttf' inside dom-to-pptx because the URL has no
 * recognisable extension — and TTF is exactly what we embed.
 */
async function downloadGoogleFonts(googleFontsHrefs) {
    if (!googleFontsHrefs.length) return [];

    const fonts       = [];
    const seenFonts   = new Set(); // one variant per family name
    const seenFileUrls = new Set();

    for (const href of googleFontsHrefs) {
        let css;
        try {
            css = (await fetchBuf(href)).toString('utf8');
        } catch (e) {
            console.warn(`[fonts] Could not fetch ${href}:`, e.message);
            continue;
        }

        const faceRe = /@font-face\s*\{([\s\S]*?)\}/g;
        let m;
        while ((m = faceRe.exec(css)) !== null) {
            const block    = m[1];
            const nameMatch = block.match(/font-family\s*:\s*['"]?([^;'"]+)['"]?/);
            const urlMatch  = block.match(/url\(['"]?(https?:\/\/fonts\.gstatic\.com[^'")\s]+)['"]?\)/);
            if (!nameMatch || !urlMatch) continue;

            const name    = nameMatch[1].trim();
            const fontUrl = urlMatch[1];

            // One face per family keeps the PPTX embeddedFontLst clean.
            if (seenFonts.has(name) || seenFileUrls.has(fontUrl)) continue;
            seenFonts.add(name);
            seenFileUrls.add(fontUrl);

            try {
                const buf = await fetchBuf(fontUrl);
                fonts.push({ name, url: `data:font/ttf;base64,${buf.toString('base64')}` });
                console.log(`[fonts] "${name}" — ${Math.round(buf.length / 1024)} KB`);
            } catch (e) {
                console.warn(`[fonts] Could not download ${fontUrl}:`, e.message);
            }
        }
    }

    console.log(`[fonts] ${fonts.length} font(s) ready for embedding`);
    return fonts;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
    const args = process.argv.slice(2);
    let outputPath = '';
    let layoutName = 'LAYOUT_16x9_1280';
    let tmpDir     = os.tmpdir();
    let htmlFiles  = [];

    for (let i = 0; i < args.length; i++) {
        if      (args[i] === '--output')    outputPath = args[++i];
        else if (args[i] === '--layout')    layoutName = args[++i];
        else if (args[i] === '--tmp-dir')   tmpDir     = args[++i];
        else if (args[i] === '--html2pptx') ++i;   // backwards compat, unused
        else if (args[i] === '--')          { htmlFiles = args.slice(i + 1); break; }
    }

    if (!outputPath || !htmlFiles.length) {
        console.error(
            'Usage: node html2pptx_runner.js --output out.pptx ' +
            '--layout LAYOUT_16x9_1280 [--tmp-dir /tmp] -- slide1.html ...'
        );
        process.exit(1);
    }

    const layout = LAYOUTS[layoutName];
    if (!layout) {
        console.error(`Unknown layout "${layoutName}". Valid: ${Object.keys(LAYOUTS).join(', ')}`);
        process.exit(1);
    }

    const domToPptxBundle = path.resolve(
        __dirname, '..', '..', 'node_modules', 'dom-to-pptx', 'dist', 'dom-to-pptx.bundle.js'
    );
    if (!fs.existsSync(domToPptxBundle)) {
        console.error(`dom-to-pptx bundle not found at: ${domToPptxBundle}`);
        console.error('Run: npm install dom-to-pptx');
        process.exit(1);
    }

    const slides = htmlFiles.map(filePath => ({
        ...parseSlideHtml(materializePseudoBackgrounds(fs.readFileSync(filePath, 'utf8'))),
        dir: path.dirname(path.resolve(filePath)),
    }));
    const slideDir = slides[0].dir;
    const orchFile = path.join(slideDir, `._orchestrator_${crypto.randomBytes(6).toString('hex')}.html`);

    let embeddedFonts = [];

    // Pre-download Google Fonts as TTF in Node.js (no CORS) so the browser
    // page can embed them via fetch('data:font/ttf;base64,...') without errors.
    const googleFontsHrefs = collectGoogleFontsHrefs(slides);
    try {
        embeddedFonts = await downloadGoogleFonts(googleFontsHrefs);
    } catch (e) {
        console.warn('[fonts] Pre-download failed, fonts will not be embedded:', e.message);
    }

    // Font Awesome: download TTF files and materialize <i> icon elements into
    // real <span> nodes so dom-to-pptx can see them (it cannot read ::before).
    const faHrefs = collectFontAwesomeHrefs(slides);
    if (faHrefs.length) {
        try {
            const { fonts: faFonts, iconMap } = await downloadFontAwesomeFonts(faHrefs);
            embeddedFonts = [...embeddedFonts, ...faFonts];
            if (Object.keys(iconMap).length) {
                slides.forEach(slide => {
                    slide.body = materializeFontAwesomeIcons(slide.body, iconMap);
                });
                console.log('[fa] Icons materialized in slide bodies');
            }
        } catch (e) {
            console.warn('[fa] Font Awesome processing failed:', e.message);
        }
    }

    fs.writeFileSync(orchFile, buildOrchestratorHtml(slides, layout, domToPptxBundle), 'utf8');

    const { chromium } = require('playwright');
    const browser = await chromium.launch();

    try {
        const context = await browser.newContext({
            viewport:        { width: layout.viewportW, height: layout.viewportH * htmlFiles.length },
            acceptDownloads: true,
        });
        const page = await context.newPage();
        page.on('pageerror', err => console.error('[page error]', err.message));
        page.on('console', msg => { if (msg.type() === 'error') console.error('[page console]', msg.text()); });

        await page.goto(toFileUrl(orchFile), { waitUntil: 'load', timeout: 60_000 });
        await page.waitForTimeout(SETTLE_MS);

        // dom-to-pptx exports descendant nodes of `.slide-host`, but it does not
        // carry over the orchestrator page background. When local theme CSS sets
        // the slide base via `html/body` (and pseudo-elements like `body::before`)
        // the slide ends up exporting onto a default white PPT background, which
        // washes out every semi-transparent shape. We scope local CSS to the host
        // above, then rasterize ONLY the host's own background/pseudo layer into a
        // real child image. Content descendants remain as native PPT text/shapes.
        await page.addStyleTag({
            content: [
                '.slide-host[data-rasterizing-bg="1"] * { visibility: hidden !important; }',
                '.slide-host[data-raster-bg="1"]::before, .slide-host[data-raster-bg="1"]::after {',
                '  content: none !important;',
                '  display: none !important;',
                '  background: none !important;',
                '}',
            ].join('\n'),
        });

        const hostCount = await page.locator('.slide-host').count();
        for (let i = 0; i < hostCount; i++) {
            const host = page.locator('.slide-host').nth(i);
            const needsRasterBg = await host.evaluate((el) => {
                function hasPaint(style) {
                    if (!style) return false;
                    const bgImage = style.backgroundImage && style.backgroundImage !== 'none';
                    const bgColor = style.backgroundColor &&
                        style.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
                        style.backgroundColor !== 'transparent';
                    return bgImage || bgColor;
                }

                return hasPaint(window.getComputedStyle(el)) ||
                    hasPaint(window.getComputedStyle(el, '::before')) ||
                    hasPaint(window.getComputedStyle(el, '::after'));
            });
            if (!needsRasterBg) continue;

            await host.evaluate(el => el.setAttribute('data-rasterizing-bg', '1'));
            const bgBuffer = await host.screenshot({ type: 'png' });
            await host.evaluate(el => el.removeAttribute('data-rasterizing-bg'));

            await host.evaluate((el, dataUrl) => {
                const bg = document.createElement('img');
                bg.src = dataUrl;
                bg.alt = '';
                bg.setAttribute('data-raster-bg-layer', '1');
                bg.style.position = 'absolute';
                bg.style.inset = '0';
                bg.style.width = '100%';
                bg.style.height = '100%';
                bg.style.pointerEvents = 'none';
                bg.style.zIndex = '0';

                el.insertBefore(bg, el.firstChild);
                el.style.background = 'none';
                el.style.backgroundImage = 'none';
                el.style.backgroundColor = 'transparent';
                el.setAttribute('data-raster-bg', '1');
            }, `data:image/png;base64,${bgBuffer.toString('base64')}`);
        }

        // Preserve Chromium's actual wrapped-line geometry for large rich-text
        // headings. If we export a multi-line heading as one reflowable PPT text
        // box, PowerPoint chooses its own wrap/line-height and the title can drift
        // into nearby pills/cards. We keep the source HTML untouched and only
        // rewrite the temporary export DOM into one absolutely positioned text box
        // per rendered browser line.
        await page.evaluate(() => {
            const HEADING_SELECTOR = '.slide-host h1, .slide-host h2, .slide-host h3, .slide-host .display, .slide-host .title, .slide-host .slide-title';
            const INLINE_TAGS = new Set(['SPAN', 'B', 'STRONG', 'I', 'EM', 'U', 'BR']);
            const LINE_GROUP_EPSILON_PX = 2;
            const WIDTH_BUFFER_PX = 16;
            const HEIGHT_BUFFER_PX = 4;

            function applyTextTransform(text, transform) {
                if (transform === 'uppercase') return text.toUpperCase();
                if (transform === 'lowercase') return text.toLowerCase();
                if (transform === 'capitalize') return text.replace(/\b\w/g, c => c.toUpperCase());
                return text;
            }

            function snapshotTextStyle(el) {
                const cs = window.getComputedStyle(el);
                return {
                    color: cs.color,
                    fontFamily: cs.fontFamily,
                    fontSize: cs.fontSize,
                    fontWeight: cs.fontWeight,
                    fontStyle: cs.fontStyle,
                    letterSpacing: cs.letterSpacing,
                    lineHeight: cs.lineHeight,
                    textDecorationLine: cs.textDecorationLine,
                    textDecorationStyle: cs.textDecorationStyle,
                    textDecorationColor: cs.textDecorationColor,
                };
            }

            function sameTextStyle(a, b) {
                return a.color === b.color &&
                    a.fontFamily === b.fontFamily &&
                    a.fontSize === b.fontSize &&
                    a.fontWeight === b.fontWeight &&
                    a.fontStyle === b.fontStyle &&
                    a.letterSpacing === b.letterSpacing &&
                    a.lineHeight === b.lineHeight &&
                    a.textDecorationLine === b.textDecorationLine &&
                    a.textDecorationStyle === b.textDecorationStyle &&
                    a.textDecorationColor === b.textDecorationColor;
            }

            function applyTextStyle(target, style) {
                target.style.color = style.color;
                target.style.fontFamily = style.fontFamily;
                target.style.fontSize = style.fontSize;
                target.style.fontWeight = style.fontWeight;
                target.style.fontStyle = style.fontStyle;
                target.style.letterSpacing = style.letterSpacing;
                target.style.lineHeight = style.lineHeight;
                target.style.textTransform = 'none';
                if (style.textDecorationLine && style.textDecorationLine !== 'none') {
                    target.style.textDecorationLine = style.textDecorationLine;
                    target.style.textDecorationStyle = style.textDecorationStyle;
                    target.style.textDecorationColor = style.textDecorationColor;
                }
            }

            function getOrCreateLine(lines, rect) {
                const midY = rect.top + rect.height / 2;
                let line = lines.find(item =>
                    midY >= item.top - LINE_GROUP_EPSILON_PX &&
                    midY <= item.bottom + LINE_GROUP_EPSILON_PX
                );
                if (line) return line;

                line = {
                    top: rect.top,
                    bottom: rect.top + rect.height,
                    left: rect.left,
                    right: rect.right,
                    fragments: [],
                };
                lines.push(line);
                return line;
            }

            function collectRenderedLines(el) {
                const lines = [];
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                let order = 0;

                while (walker.nextNode()) {
                    const textNode = walker.currentNode;
                    const rawText = textNode.nodeValue || '';
                    if (!rawText.length) continue;

                    const styleSource = textNode.parentElement || el;
                    const style = snapshotTextStyle(styleSource);
                    const displayText = applyTextTransform(rawText, window.getComputedStyle(styleSource).textTransform);

                    for (let i = 0; i < rawText.length; i++) {
                        const range = document.createRange();
                        range.setStart(textNode, i);
                        range.setEnd(textNode, i + 1);
                        const rect = Array.from(range.getClientRects()).find(r => r.width > 0.1 && r.height > 0.1);
                        if (!rect) continue;

                        const line = getOrCreateLine(lines, rect);
                        line.top = Math.min(line.top, rect.top);
                        line.bottom = Math.max(line.bottom, rect.top + rect.height);
                        line.left = Math.min(line.left, rect.left);
                        line.right = Math.max(line.right, rect.right);
                        line.fragments.push({
                            text: displayText.slice(i, i + 1),
                            style,
                            order,
                        });
                        order += 1;
                    }
                }

                lines.sort((a, b) => a.top - b.top || a.left - b.left);

                return lines.map(line => {
                    const merged = [];
                    line.fragments.sort((a, b) => a.order - b.order);

                    for (const fragment of line.fragments) {
                        const last = merged[merged.length - 1];
                        if (last && sameTextStyle(last.style, fragment.style) && fragment.order === last.orderEnd + 1) {
                            last.text += fragment.text;
                            last.orderEnd = fragment.order;
                        } else {
                            merged.push({ ...fragment, orderEnd: fragment.order });
                        }
                    }

                    return {
                        top: line.top,
                        left: line.left,
                        width: Math.max(0, line.right - line.left),
                        height: Math.max(0, line.bottom - line.top),
                        fragments: merged
                            .map(({ orderEnd, ...fragment }) => fragment)
                            .filter(fragment => fragment.text.length > 0),
                    };
                }).filter(line =>
                    line.width > 0.5 &&
                    line.height > 0.5 &&
                    line.fragments.some(fragment => fragment.text.trim().length > 0)
                );
            }

            for (const el of document.querySelectorAll(HEADING_SELECTOR)) {
                const cs = window.getComputedStyle(el);
                const fontSize = parseFloat(cs.fontSize) || 0;
                if (fontSize < 24) continue;

                const hasInlineChildren = Array.from(el.children).some(child => INLINE_TAGS.has(child.tagName));
                if (!hasInlineChildren) continue;

                const lines = collectRenderedLines(el);
                if (lines.length < 2) continue;

                const parent = el.parentElement;
                if (!parent) continue;
                if (window.getComputedStyle(parent).position === 'static') {
                    parent.style.position = 'relative';
                }

                const parentRect = parent.getBoundingClientRect();
                const baseStyle = snapshotTextStyle(el);

                for (const line of lines) {
                    const lineNode = document.createElement('div');
                    lineNode.setAttribute('data-pptx-preserved-line', '1');
                    applyTextStyle(lineNode, baseStyle);
                    lineNode.style.position = 'absolute';
                    lineNode.style.left = (line.left - parentRect.left) + 'px';
                    lineNode.style.top = (line.top - parentRect.top) + 'px';
                    lineNode.style.width = (line.width + WIDTH_BUFFER_PX) + 'px';
                    lineNode.style.height = (line.height + HEIGHT_BUFFER_PX) + 'px';
                    lineNode.style.margin = '0';
                    lineNode.style.padding = '0';
                    lineNode.style.border = '0';
                    lineNode.style.background = 'none';
                    lineNode.style.overflow = 'visible';
                    lineNode.style.whiteSpace = 'pre';
                    lineNode.style.pointerEvents = 'none';
                    lineNode.style.textAlign = cs.textAlign;
                    lineNode.style.zIndex = cs.zIndex !== 'auto' ? cs.zIndex : '0';

                    for (const fragment of line.fragments) {
                        if (!fragment.text) continue;
                        if (sameTextStyle(fragment.style, baseStyle)) {
                            lineNode.appendChild(document.createTextNode(fragment.text));
                        } else {
                            const span = document.createElement('span');
                            applyTextStyle(span, fragment.style);
                            span.textContent = fragment.text;
                            lineNode.appendChild(span);
                        }
                    }

                    parent.appendChild(lineNode);
                }

                el.style.visibility = 'hidden';
                el.setAttribute('data-pptx-preserve-lines-source', '1');
            }
        });

        // Materialise CSS `filter` and `opacity` on <img> elements so that
        // dom-to-pptx (which uses getComputedStyle + getBoundingClientRect but
        // does NOT translate CSS filter/opacity into PPTX image effects) receives
        // a pre-processed image with the visual appearance already baked in.
        //
        // For each <img> that has a non-trivial filter or opacity:
        //   1. Draw the image to a canvas with ctx.filter + ctx.globalAlpha so
        //      both effects are baked into the PNG pixel data (alpha channel).
        //   2. Replace img.src with the canvas data-URL.
        //   3. Reset the CSS filter and opacity to neutral so dom-to-pptx sees
        //      a plain image and does not double-apply any effect.
        await page.evaluate(() => {
            /**
             * Walk up the DOM from `el` and multiply together all `opacity`
             * values set on ancestors (including el itself), stopping at the
             * document root.  This gives the effective visual opacity.
             */
            function effectiveOpacity(el) {
                let opacity = 1;
                let node = el;
                while (node && node !== document.documentElement) {
                    const o = parseFloat(window.getComputedStyle(node).opacity);
                    if (!isNaN(o)) opacity *= o;
                    node = node.parentElement;
                }
                return opacity;
            }

            /**
             * Bake CSS filter + opacity into a canvas and return a data URL.
             * The canvas alpha channel carries the opacity so no separate PPTX
             * transparency attribute is needed.
             */
            function bakeImage(img, filterValue, opacity) {
                const w = img.naturalWidth  || img.width  || 1;
                const h = img.naturalHeight || img.height || 1;
                const canvas = document.createElement('canvas');
                canvas.width  = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                if (filterValue !== 'none') ctx.filter = filterValue;
                ctx.globalAlpha = Math.max(0, Math.min(1, opacity));
                ctx.drawImage(img, 0, 0, w, h);
                return canvas.toDataURL('image/png');
            }

            for (const img of document.querySelectorAll('img')) {
                const cs      = window.getComputedStyle(img);
                const filter  = cs.filter || cs.webkitFilter || 'none';
                const opacity = effectiveOpacity(img);

                if (filter === 'none' && opacity >= 1) continue;

                try {
                    img.src = bakeImage(img, filter, opacity);
                    img.style.filter  = 'none';
                    img.style.opacity = '1';
                } catch (e) {
                    // tainted canvas (cross-origin image) — skip
                }
            }
        });

        // Bake rgba text colours to solid (PPTX text boxes have no alpha-channel
        // colour support) and freeze non-default flex layouts to explicit absolute
        // coordinates so dom-to-pptx gets concrete positions rather than having
        // to re-implement justify-content / align-items logic.
        await page.evaluate(() => {
            // ── helpers ───────────────────────────────────────────────────────
            function parseRgba(str) {
                const m = str.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)/);
                return m ? { r: +m[1], g: +m[2], b: +m[3], a: m[4] !== undefined ? +m[4] : 1 } : null;
            }

            // Walk up the DOM to find the first ancestor with a non-transparent bg.
            function effectiveBg(el) {
                for (let n = el.parentElement; n && n !== document.documentElement; n = n.parentElement) {
                    const bg = parseRgba(window.getComputedStyle(n).backgroundColor);
                    if (bg && bg.a > 0.01) return bg;
                }
                return { r: 0, g: 0, b: 0, a: 1 }; // fall back to black
            }

            // ── 1. Solid-ify semi-transparent text colours ────────────────────
            for (const el of document.querySelectorAll('*')) {
                const cs = window.getComputedStyle(el);
                const fg = parseRgba(cs.color);
                if (!fg || fg.a >= 1) continue;
                const bg = effectiveBg(el);
                el.style.color = `rgb(${
                    Math.round(bg.r * (1 - fg.a) + fg.r * fg.a)},${
                    Math.round(bg.g * (1 - fg.a) + fg.g * fg.a)},${
                    Math.round(bg.b * (1 - fg.a) + fg.b * fg.a)})`;
            }

            // ── 2. Re-parent space-between/around/evenly flex children ──────────
            // dom-to-pptx treats the flex container as one text box and collapses
            // all children into it, ignoring individual child positions.  The only
            // reliable fix is to move each child OUT of the container and attach it
            // directly to the nearest positioned ancestor (the slide root), with
            // explicit absolute coordinates derived from the browser's own layout.
            //
            // Two-phase: collect ALL position snapshots first (zero DOM mutations),
            // then re-parent in a second pass so earlier moves don't corrupt later
            // getBoundingClientRect reads.
            const DISTRIBUTION_JUSTIFY = new Set(['space-between', 'space-around', 'space-evenly']);

            // Phase 1: snapshot — zero DOM mutations.
            const freezeOps = [];
            for (const container of document.querySelectorAll('*')) {
                const cs = window.getComputedStyle(container);
                if (cs.display !== 'flex' && cs.display !== 'inline-flex') continue;
                if (!DISTRIBUTION_JUSTIFY.has(cs.justifyContent)) continue;

                // Walk up to find the nearest positioned ancestor — this becomes
                // the new containing block for the re-parented children.
                let newParent = container.parentElement;
                while (newParent && newParent !== document.body) {
                    if (window.getComputedStyle(newParent).position !== 'static') break;
                    newParent = newParent.parentElement;
                }
                if (!newParent) continue;

                const containerRect = container.getBoundingClientRect();
                const parentRect = newParent.getBoundingClientRect();
                const children   = Array.from(container.children);
                const childRects = children.map(c => c.getBoundingClientRect());

                freezeOps.push({ container, containerRect, newParent, parentRect, children, childRects });
            }

            // Phase 2: re-parent — all positions already captured.
            for (const { container, containerRect, newParent, parentRect, children, childRects } of freezeOps) {
                // Keep the container's original slot in normal flow. Without this,
                // moving its children out can make the empty flex box collapse and
                // pull later sections (like the main diagram) upward.
                container.style.width = containerRect.width + 'px';
                container.style.height = containerRect.height + 'px';
                container.style.minWidth = containerRect.width + 'px';
                container.style.minHeight = containerRect.height + 'px';
                container.style.maxWidth = containerRect.width + 'px';
                container.style.maxHeight = containerRect.height + 'px';
                container.style.flex = '0 0 auto';

                children.forEach((child, i) => {
                    const r = childRects[i];
                    child.style.position = 'absolute';
                    child.style.left     = (r.left - parentRect.left) + 'px';
                    child.style.top      = (r.top  - parentRect.top)  + 'px';
                    child.style.width    = r.width  + 'px';
                    newParent.appendChild(child); // lifts child out of the flex container
                });
                // Hide the now-empty container so dom-to-pptx skips it.
                container.style.visibility = 'hidden';
            }
        });

        const [download] = await Promise.all([
            page.waitForEvent('download', { timeout: EXPORT_TIMEOUT_MS }),
            page.evaluate(({ fileName, fonts }) => {
                const hosts = Array.from(document.querySelectorAll('.slide-host'));
                return window.domToPptx.exportToPptx(hosts, {
                    fileName,
                    // svgAsVector: false — rasterise SVGs; the vector path (v1.1.5) can
                    // produce malformed XML that causes PowerPoint's "Repair" dialog.
                    svgAsVector:    false,
                    // autoEmbedFonts: false — we supply pre-downloaded TTF fonts via the
                    // `fonts` option instead. Each data: URI is fetched by the browser
                    // without CORS issues, and TTF is the format PowerPoint can embed.
                    autoEmbedFonts: false,
                    fonts,
                });
            }, { fileName: path.basename(outputPath), fonts: embeddedFonts }),
        ]);

        await download.saveAs(outputPath);
        console.log(`Saved: ${outputPath}`);
        console.log(`Converted ${htmlFiles.length} slide(s)`);

        await context.close();
    } finally {
        await browser.close();
        try { fs.unlinkSync(orchFile); } catch (_) {}
    }
}

main().catch(err => {
    console.error(err.message || String(err));
    process.exit(1);
});
