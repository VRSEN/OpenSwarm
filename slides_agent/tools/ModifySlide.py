"""
Modify an existing slide by generating HTML with a sub-agent.

Flow: InsertNewSlides creates blank placeholders + plan, then ModifySlide generates/edits slide HTML.
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agency_swarm import Agent, ModelSettings, Reasoning
from agency_swarm.tools import BaseTool, ToolOutputText, tool_output_image_from_path
from agents.extensions.models.litellm_model import LitellmModel
from openai import AsyncOpenAI
from pydantic import Field

from .slide_file_utils import get_project_dir
from .slide_html_utils import (
    ensure_full_html,
    list_slide_filenames,
    validate_html,
    _strip_html_to_text,
)
from .template_registry import load_template_index, save_template_index, template_path
# Per-project locks for the template-index read-modify-write.
_index_locks: dict[str, threading.Lock] = {}
_index_locks_guard = threading.Lock()


def _index_lock_for(project_dir: Path) -> threading.Lock:
    key = str(project_dir)
    with _index_locks_guard:
        if key not in _index_locks:
            _index_locks[key] = threading.Lock()
        return _index_locks[key]


def _strip_base64_images(html: str) -> str:
    """Replace base64 data URI references with short placeholders.

    Covers both src="data:..." attributes and url('data:...') CSS values.
    Prevents context-window overflow when feeding previously-processed HTML
    back to the sub-agent as a baseline.
    """
    # Only strip data:image/ URIs — never touch data:text/css or other non-image blobs
    html = re.sub(r'src=(["\'])data:image/[^"\']+\1', r'src=\1[image]\1', html)
    html = re.sub(r'url\((["\']?)data:image/[^"\')\s]+\1\)', r'url(\1[image]\1)', html)
    html = re.sub(r'(href|xlink:href|data)=(["\'])data:image/[^"\']+\2', r'\1=\2[image]\2', html)
    return html


def _convert_css_bg_images_to_img_tags(html: str) -> str:
    """Convert CSS background-image to <img> tags so dom-to-pptx can render them.

    Handles two patterns:
      1. Inline style:  <div style="background-image: url(img.png)">
      2. Class-based:   .cls { background-image: url(img.png) } + <div class="cls">

    For each match an absolutely-positioned <img> is injected as the first child
    and background-image/size/position/repeat are stripped from the CSS.
    Accepts both local paths and data: URIs (data URIs are kept as-is in the src).
    """
    _BG_STRIP_RE = re.compile(
        r'\bbackground-image\s*:\s*url\([^)]*\)\s*;?\s*'
        r'|\bbackground-size\s*:\s*[^;]+;\s*'
        r'|\bbackground-position\s*:\s*[^;]+;\s*'
        r'|\bbackground-repeat\s*:\s*[^;]+;\s*',
        re.IGNORECASE,
    )

    def _img_tag(src: str) -> str:
        return (
            f'<img src="{src}" alt="" '
            f'style="position:absolute;top:0;left:0;width:100%;height:100%;'
            f'object-fit:cover;z-index:0;" />'
        )

    def _should_convert(url_arg: str) -> bool:
        """Convert both local image paths and data:image/ URIs."""
        if url_arg.startswith("data:image/"):
            return True
        if url_arg.startswith(("data:", "http://", "https://", "file://")):
            return False
        return _is_image_path(url_arg)

    # ── 1. Inline style="...background-image: url(...)..." ───────────────────
    inline_re = re.compile(
        r'(<[a-zA-Z][^>]*?style=["\'])([^"\']*?background-image\s*:\s*url\(([^)]+)\)[^"\']*?)(["\'][^>]*>)',
        re.IGNORECASE,
    )

    def rewrite_inline(m: re.Match) -> str:
        before, style_val, url_raw, after = m.group(1), m.group(2), m.group(3), m.group(4)
        url_arg = url_raw.strip("\"' ")
        if not _should_convert(url_arg):
            return m.group(0)
        clean = _BG_STRIP_RE.sub('', style_val).strip().rstrip(';')
        return f'{before}{clean}{after}{_img_tag(url_arg)}'

    html = inline_re.sub(rewrite_inline, html)

    # ── 2. Class-based rules in <style> blocks ───────────────────────────────
    # Collect class → url mapping from <style> blocks
    style_block_re = re.compile(r'<style[^>]*>(.*?)</style>', re.IGNORECASE | re.DOTALL)
    css_class_bg_re = re.compile(
        r'\.([a-zA-Z_-][\w-]*)\s*\{([^}]*?background-image\s*:\s*url\(([^)]+)\)[^}]*?)\}',
        re.IGNORECASE | re.DOTALL,
    )

    class_to_url: dict[str, str] = {}
    for style_m in style_block_re.finditer(html):
        for rule_m in css_class_bg_re.finditer(style_m.group(1)):
            cls = rule_m.group(1)
            url_arg = rule_m.group(3).strip("\"' ")
            if _should_convert(url_arg):
                class_to_url[cls] = url_arg

    if not class_to_url:
        return html

    # Strip background-image from matching rules in <style> blocks
    def rewrite_style_block(style_m: re.Match) -> str:
        css = style_m.group(1)
        def clean_rule(rule_m: re.Match) -> str:
            cls = rule_m.group(1)
            if cls not in class_to_url:
                return rule_m.group(0)
            cleaned_body = _BG_STRIP_RE.sub('', rule_m.group(2)).strip().rstrip(';')
            return f'.{cls} {{{cleaned_body}}}'
        return f'<style>{css_class_bg_re.sub(clean_rule, css)}</style>'

    html = style_block_re.sub(rewrite_style_block, html)

    # Inject <img> as first child of elements that carry a matched class
    class_pattern = '|'.join(re.escape(c) for c in class_to_url)
    element_re = re.compile(
        rf'(<[a-zA-Z][^>]*?class=["\'][^"\']*?(?:{class_pattern})[^"\']*?["\'][^>]*>)',
        re.IGNORECASE,
    )

    def inject_img(m: re.Match) -> str:
        opening = m.group(1)
        # Find which class matched
        classes = re.search(r'class=["\']([^"\']+)["\']', opening, re.IGNORECASE)
        if not classes:
            return opening
        for cls in classes.group(1).split():
            if cls in class_to_url:
                return f'{opening}{_img_tag(class_to_url[cls])}'
        return opening

    html = element_re.sub(inject_img, html)
    return html


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".avif"}


def _is_image_path(src: str) -> bool:
    return Path(src.split("?")[0]).suffix.lower() in _IMAGE_EXTENSIONS


def _embed_local_images_as_base64(html: str, project_dir: Path) -> str:
    """Replace local image references with base64 data URIs.

    Handles HTML src=, CSS url(), SVG href/xlink:href, and <object data=>.
    Only processes paths with known image file extensions to avoid
    accidentally encoding scripts, stylesheets, or fonts.
    """
    def _encode(src: str) -> str | None:
        if (
            src.startswith("data:")
            or src.startswith("http://")
            or src.startswith("https://")
            or src.startswith("file://")
            or not _is_image_path(src)
        ):
            return None
        img_path = (project_dir / src).resolve()
        if not img_path.exists():
            return None
        mime, _ = mimetypes.guess_type(str(img_path))
        mime = mime or "image/png"
        encoded = base64.b64encode(img_path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def replace_src(match: re.Match) -> str:
        quote, src = match.group(1), match.group(2)
        data_uri = _encode(src)
        return f"src={quote}{data_uri}{quote}" if data_uri else match.group(0)

    def replace_css_url(match: re.Match) -> str:
        quote, src = match.group(1), match.group(2)
        data_uri = _encode(src)
        return f"url({quote}{data_uri}{quote})" if data_uri else match.group(0)

    def replace_href(match: re.Match) -> str:
        attr, quote, src = match.group(1), match.group(2), match.group(3)
        data_uri = _encode(src)
        return f'{attr}={quote}{data_uri}{quote}' if data_uri else match.group(0)

    html = re.sub(r'src=(["\'])((?!data:|https?://|file://)[^"\']+)\1', replace_src, html)
    html = re.sub(r'url\((["\']?)((?!data:|https?://|file://)[^"\')\s]+)\1\)', replace_css_url, html)
    html = re.sub(
        r'(href|xlink:href|data)=(["\'])((?!data:|https?://|file://|#)[^"\']+)\2',
        replace_href,
        html,
    )
    return html


_HTML_WRITER_MODEL_CLAUDE = "anthropic/claude-sonnet-4-6"
_HTML_WRITER_MODEL_OAI = "gpt-5.2-codex"
_HTML_WRITER_MAX_ATTEMPTS = 3


def _get_caller_openai_client(tool) -> "AsyncOpenAI | None":
    ctx = getattr(tool, "_context", None)
    master = getattr(ctx, "context", None)
    agent_name = getattr(master, "current_agent_name", None)
    agents = getattr(master, "agents", {})
    agent = agents.get(agent_name) if agent_name else None
    model = getattr(agent, "model", None)
    client = getattr(model, "_client", None)
    return client if isinstance(client, AsyncOpenAI) else None


def _make_html_writer_agent(tool=None) -> Agent:
    """Create a fresh, stateless agent instance for one ModifySlide call.

    Model priority:
    1. ANTHROPIC_API_KEY in env → Claude Sonnet 4.6 (best HTML quality)
    2. Calling agent's OpenAI client (browser auth / per-request ClientConfig)
    3. AsyncOpenAI() default (env vars)
    """
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        model = LitellmModel(model=_HTML_WRITER_MODEL_CLAUDE, api_key=anthropic_key)
    else:
        from agents import OpenAIResponsesModel
        from openai import AsyncOpenAI
        client = (tool and _get_caller_openai_client(tool)) or AsyncOpenAI()
        model = OpenAIResponsesModel(model=_HTML_WRITER_MODEL_OAI, openai_client=client)
    return Agent(
        name="Slide HTML Writer",
        description="Generates complete slide HTML from task briefs.",
        instructions=_read_html_writer_instructions(),
        tools=[],
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto"),
            verbosity="medium",
        ),
    )


def _extract_html_from_output(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    code_block = re.search(r"```(?:html)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    html_start = re.search(r"(?is)(<!doctype html>|<html\b)", raw)
    if html_start:
        return raw[html_start.start() :].strip()
    body_start = re.search(r"(?is)<body\b", raw)
    if body_start:
        return raw[body_start.start() :].strip()
    return raw


def _read_html_writer_instructions() -> str:
    path = Path(__file__).with_name("html_writer_instructions.md")
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return "You generate slide HTML. Return only HTML content."


def _read_theme_css(project_dir: Path) -> str:
    theme_path = project_dir / "_theme.css"
    if not theme_path.exists():
        return ""
    try:
        return theme_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _extract_used_classes(html_content: str, limit: int = 120) -> list[str]:
    classes: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'class\s*=\s*["\']([^"\']+)["\']', html_content, flags=re.IGNORECASE):
        raw = match.group(1)
        for cls in re.split(r"\s+", raw.strip()):
            if not cls or cls in seen:
                continue
            seen.add(cls)
            classes.append(cls)
            if len(classes) >= limit:
                return classes
    return classes


def _build_main_text_contents(project_dir: Path, current_slide: str) -> str:
    """Return a MAIN_TEXT_CONTENTS block with a one-line text snippet per slide.

    Mirrors the block the main agent receives each turn so the HTML writer
    sub-agent has the same deck-wide context (what's on each slide, what slide
    number it is currently editing, total count).
    """
    slides = list_slide_filenames(project_dir)
    if not slides:
        return ""
    lines = ["<MAIN_TEXT_CONTENTS>"]
    for i, name in enumerate(slides, 1):
        try:
            text = _strip_html_to_text((project_dir / name).read_text(encoding="utf-8"))
        except Exception:
            text = "(unreadable)"
        marker = " ← YOU ARE EDITING THIS SLIDE" if name == current_slide else ""
        lines.append(f"  <SLIDE_{i}>{text}</SLIDE_{i}>{marker}")
    lines.append("</MAIN_TEXT_CONTENTS>")
    return "\n".join(lines)



def _build_sub_run_prompt(
    *,
    task_brief: str,
    slide_name: str,
    total_pages: int,
    main_text_contents: str,
    base_html: str,
    current_html: str | None = None,
    theme_css: str,
    retry_validation_error: str = "",
    previous_failed_html: str | None = None,
) -> str:
    """Build the per-call user message for the HTML writer sub-agent.

    Design guidelines and validation rules are in the agent's system prompt
    (set once at agent creation). This message carries only the dynamic,
    per-slide context that changes with every call.

    When `current_html` is provided it means a saved template (not the slide itself)
    is being used as the layout baseline. The current slide content is shown
    separately so the writer knows what already exists on the slide.

    When `previous_failed_html` is provided (retry ≥ 2), the writer receives
    its own previous output so it can surgically fix the specific violations
    rather than regenerating from scratch.
    """
    deck_context = (
        f"Deck overview — {total_pages} slide(s) total:\n{main_text_contents}"
        if main_text_contents
        else f"Total slides in deck: {total_pages}"
    )
    retry_block = (
        f"\n\nVALIDATION FEEDBACK FROM PREVIOUS ATTEMPT (fix these before returning):\n{retry_validation_error}"
        if retry_validation_error
        else ""
    )
    previous_attempt_block = (
        "\n\nYOUR PREVIOUS ATTEMPT (the HTML you returned that failed validation — fix it, do not regenerate from scratch):\n"
        "<PREVIOUS_ATTEMPT>\n"
        f"{previous_failed_html}\n"
        "</PREVIOUS_ATTEMPT>"
        if previous_failed_html
        else ""
    )

    if current_html is not None:
        # Template mode: base_html is a saved layout skeleton, current_html is the
        # live slide. Show both so the writer uses the template structure but
        # understands the slide's existing content.
        html_section = (
            "LAYOUT_TEMPLATE_HTML (use this as the structural/design baseline — "
            "adopt its layout, colours, and component patterns):\n"
            "<LAYOUT_TEMPLATE>\n"
            f"{base_html}\n"
            "</LAYOUT_TEMPLATE>\n\n"
            "CURRENT_SLIDE_HTML (the slide as it exists now — understand its content "
            "but replace the layout with the template above):\n"
            "<CURRENT_SLIDE>\n"
            f"{current_html}\n"
            "</CURRENT_SLIDE>\n"
        )
    else:
        # Direct edit mode: base_html IS the current slide. Modify it in place.
        html_section = (
            "CURRENT_SLIDE_HTML (edit this slide in place — preserve everything "
            "not mentioned in the task brief):\n"
            "<CURRENT_SLIDE>\n"
            f"{base_html}\n"
            "</CURRENT_SLIDE>\n"
        )

    return (
        f"Target slide: {slide_name}\n"
        f"{deck_context}\n\n"
        "TASK_BRIEF:\n"
        f"{task_brief.strip()}\n\n"
        f"{html_section}\n"
        "CURRENT_THEME_CSS (authoritative design tokens — reuse, do not contradict):\n"
        "<THEME_CSS>\n"
        f"{theme_css}\n"
        "</THEME_CSS>\n\n"
        "USED_CLASSES_IN_CURRENT_SLIDE:\n"
        f"{', '.join(_extract_used_classes(base_html))}"
        f"{previous_attempt_block}"
        f"{retry_block}"
    )


def _screenshot_html_slide(html_path: Path) -> tuple[Any | None, str]:
    """Render the slide HTML in a headless browser and return (ToolOutputImage | None, error_msg).

    Returns (None, reason) on failure so the caller can include the reason in the tool output.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=20_000)
            page.wait_for_timeout(800)  # let JS and fonts settle
            tmp = Path(tempfile.mktemp(suffix=".jpg"))
            page.screenshot(
                path=str(tmp),
                clip={"x": 0, "y": 0, "width": 1280, "height": 720},
                type="jpeg",
                quality=80,
            )
            browser.close()
        return tool_output_image_from_path(tmp), ""
    except Exception as exc:
        return None, str(exc)




class ModifySlide(BaseTool):
    """Generate/update slide HTML from task brief via sub-agent."""

    project_name: str = Field(..., description="Presentation project folder name under ./mnt/<project_name>/presentations. Only provide the project_name in this field.")
    slide_name: str = Field(..., description="Slide filename (e.g., slide_01 or slide_01.html)")
    task_brief: str = Field(..., description="What to change on this slide. Do not include any HTML in the tool input. HTML is written by the sub-agent inside this tool.")
    existing_template_key: str | None = Field(default=None, description="Optional template key to load as baseline")
    save_as_template_key: str | None = Field(default=None, description="Optional template key to save resulting slide")
    save_as_template_name: str | None = Field(default=None, description="Optional display name for saved template")

    async def run(self):
        project_dir = get_project_dir(self.project_name)
        if not project_dir.exists():
            return f"Project not found: {project_dir}"

        slide_filename = self.slide_name if self.slide_name.lower().endswith(".html") else f"{self.slide_name}.html"
        slide_path = project_dir / slide_filename
        if not slide_path.exists():
            return f"Slide not found: {slide_filename}"

        index_data = load_template_index(project_dir)
        current_html = _strip_base64_images(slide_path.read_text(encoding="utf-8"))
        base_html = current_html
        using_template = False

        if self.existing_template_key:
            key = self.existing_template_key.strip()
            meta = index_data.get(key)
            if not meta:
                return f"Template key not found: {key}"
            path = template_path(project_dir, key)
            if not path.exists():
                return f"Template file missing for key '{key}': {path.name}"
            base_html = _strip_base64_images(path.read_text(encoding="utf-8"))
            using_template = True

        total_pages = len([p for p in project_dir.glob("*.html")])
        theme_css = _read_theme_css(project_dir)
        main_text_contents = _build_main_text_contents(project_dir, slide_filename)

        writer = _make_html_writer_agent(tool=self)

        sub_results: list[Any] = []
        last_validation_error = ""
        previous_failed_html: str | None = None
        final_html = ""
        used_scaffold = False

        for attempt in range(1, _HTML_WRITER_MAX_ATTEMPTS + 1):
            prompt = _build_sub_run_prompt(
                task_brief=self.task_brief,
                slide_name=slide_filename,
                total_pages=total_pages,
                main_text_contents=main_text_contents,
                base_html=base_html,
                current_html=current_html if using_template else None,
                theme_css=theme_css,
                retry_validation_error=last_validation_error,
                previous_failed_html=previous_failed_html,
            )

            try:
                final_result = await writer.get_response(prompt)
            except Exception as exc:
                import traceback
                last_validation_error = f"Sub-agent error (attempt {attempt}): {exc}\n{traceback.format_exc()}"
                continue
            sub_results.append(final_result)

            # No result object means the framework swallowed an API-level error
            # (e.g. rate limit).  Extract whatever error detail is available.
            if final_result is None:
                last_validation_error = f"Sub-agent returned no result on attempt {attempt} (possible rate limit or API error)."
                continue
            api_error = getattr(final_result, "error", None) or getattr(final_result, "last_error", None)
            if api_error:
                last_validation_error = f"Sub-agent API error (attempt {attempt}): {api_error}"
                continue

            output_text = str(getattr(final_result, "final_output", "") or "")
            candidate_html = _extract_html_from_output(output_text)
            if not candidate_html:
                last_validation_error = f"Model returned empty output on attempt {attempt}."
                continue

            full_html, used_scaffold = ensure_full_html(candidate_html)
            validation = await asyncio.to_thread(validate_html, full_html, project_dir, used_scaffold)
            if validation.get("valid"):
                final_html = full_html
                break
            last_validation_error = str(validation.get("error", "Unknown validation error")).strip()
            previous_failed_html = full_html

        if not final_html:
            return f"HTML validation failed after {_HTML_WRITER_MAX_ATTEMPTS} attempts:\n{last_validation_error}"

        final_html = _convert_css_bg_images_to_img_tags(final_html)
        final_html = _embed_local_images_as_base64(final_html, project_dir)
        slide_path.write_text(final_html, encoding="utf-8")
        save_note = ""
        if self.save_as_template_key:
            key = self.save_as_template_key.strip()
            t_path = template_path(project_dir, key)
            t_path.write_text(final_html, encoding="utf-8")
            with _index_lock_for(project_dir):
                fresh_index = load_template_index(project_dir)
                fresh_index[key] = {
                    "name": (self.save_as_template_name or key).strip(),
                    "source_slide": slide_filename,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                save_template_index(project_dir, fresh_index)
            save_note = f"\nSaved template: {key}."

        success_msg = f"Updated {slide_filename}.{save_note}"

        screenshot, screenshot_err = await asyncio.to_thread(_screenshot_html_slide, slide_path)
        if screenshot is not None:
            return [ToolOutputText(text=success_msg), screenshot]
        if screenshot_err:
            return f"{success_msg}\n Screenshot failed: {screenshot_err}"
        return success_msg

if __name__ == "__main__":
    modify_slide = ModifySlide(project_name="universe_5slide_deck", slide_name="slide_06", task_brief="""Generate a plain string saying hello world""")
    print(asyncio.run(modify_slide.run()))