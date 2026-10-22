import { fetchJson, requireOnboarding, renderNav, formatEsbiInstructions } from "./app.js";

const AGENCY_PATH = "/Architect_Blueprint/get_response";
const STUDIO_AGENT = "Orchestrator";
const USER_ID = "default";

const STARTERS = [
  "Create a one-page financial summary PDF using my intake numbers",
  "Build a 5-slide pitch deck for my business",
  "Design a single-slide pitch card with my trade and value prop",
  "Generate a professional hero image for my brand",
  "Create a 15-second promo video script and video for my offer",
];

let financialSummary = null;
let architectDossier = null;
let chatHistory = [];

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdown(source) {
  const lines = String(source).split("\n");
  const out = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };
  for (const raw of lines) {
    const trimmed = raw.trim();
    if (!trimmed) {
      closeList();
      continue;
    }
    const bulletMatch = trimmed.match(/^[-*•]\s+(.+)/);
    if (bulletMatch) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inlineMarkdown(bulletMatch[1])}</li>`);
      continue;
    }
    closeList();
    out.push(`<p>${inlineMarkdown(trimmed)}</p>`);
  }
  closeList();
  return `<div class="chat-md">${out.join("")}</div>`;
}

function appendMessage(role, text, { markdown = false } = {}) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  div.className = role === "user" ? "chat-user" : "chat-assistant";
  if (markdown && role === "assistant") {
    div.innerHTML = renderMarkdown(text);
  } else {
    div.textContent = text;
  }
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function formatBytes(n) {
  if (!n) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function previewInlineUrl(url) {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}inline=true`;
}

function hideAllPreviewNodes() {
  document.getElementById("preview-frame").classList.add("hidden");
  document.getElementById("preview-image").classList.add("hidden");
  document.getElementById("preview-video").classList.add("hidden");
  document.getElementById("preview-markdown").classList.add("hidden");
  document.getElementById("preview-frame-wrap").classList.remove("preview-slide");
}

async function showPreview(artifact) {
  if (!artifact?.preview_url && !artifact?.download_url) return;
  const section = document.getElementById("preview-section");
  const url = previewInlineUrl(artifact.preview_url || artifact.download_url);
  const type = artifact.preview_type || "html";
  const title = document.getElementById("preview-title");
  const download = document.getElementById("preview-download");

  hideAllPreviewNodes();
  section.classList.remove("hidden");
  title.textContent = artifact.name || "Preview";
  download.href = artifact.download_url || url;

  const frame = document.getElementById("preview-frame");
  const img = document.getElementById("preview-image");
  const video = document.getElementById("preview-video");
  const mdEl = document.getElementById("preview-markdown");
  const wrap = document.getElementById("preview-frame-wrap");

  if (type === "image") {
    img.src = url;
    img.classList.remove("hidden");
    return;
  }
  if (type === "video") {
    video.src = url;
    video.classList.remove("hidden");
    return;
  }
  if (type === "markdown") {
    try {
      const res = await fetch(url);
      mdEl.textContent = await res.text();
    } catch {
      mdEl.textContent = "Could not load markdown preview.";
    }
    mdEl.classList.remove("hidden");
    return;
  }
  if (type === "pitch_card") {
    wrap.classList.add("preview-slide");
  }
  frame.src = url;
  frame.classList.remove("hidden");
}

function closePreview() {
  hideAllPreviewNodes();
  document.getElementById("preview-frame").src = "about:blank";
  document.getElementById("preview-section").classList.add("hidden");
}

function pickPreviewFromResult(result) {
  if (result?.preview) return result.preview;
  const files = result?.files || [];
  const order = ["html", "pdf", "pitch_card", "markdown", "image"];
  for (const kind of order) {
    const hit = files.find((f) => f.preview_type === kind);
    if (hit) return { ...hit, name: result.document_name };
  }
  return files[0] ? { ...files[0], name: result.document_name } : null;
}

async function refreshArtifacts() {
  const listEl = document.getElementById("artifact-list");
  const emptyEl = document.getElementById("artifact-empty");
  try {
    const data = await fetchJson("/studio/artifacts");
    const items = data.artifacts || [];
    if (!items.length) {
      listEl.innerHTML = "";
      emptyEl.classList.remove("hidden");
      return;
    }
    emptyEl.classList.add("hidden");
    listEl.innerHTML = items
      .map(
        (a) => `
      <li class="artifact-item">
        <span class="artifact-cat">${a.category}</span>
        <a href="${a.download_url}" target="_blank" rel="noopener">${escapeHtml(a.name)}</a>
        <span class="muted small">${formatBytes(a.size_bytes)}</span>
        <div class="artifact-actions">
          ${a.preview_url ? `<button type="button" class="btn btn-secondary btn-sm artifact-preview" data-path="${escapeHtml(a.path)}">Preview</button>` : ""}
          <a class="btn btn-secondary btn-sm" href="${a.download_url}" target="_blank" rel="noopener">Download</a>
        </div>
      </li>`
      )
      .join("");

    listEl.querySelectorAll(".artifact-preview").forEach((btn) => {
      btn.onclick = () => {
        const item = items.find((x) => x.path === btn.dataset.path);
        if (item) showPreview(item);
      };
    });
  } catch {
    listEl.innerHTML = "";
    emptyEl.textContent = "Could not load files — is python server.py running?";
    emptyEl.classList.remove("hidden");
  }
}

async function checkStudioAvailable() {
  try {
    const res = await fetch(`${AGENCY_PATH.replace("/get_response", "/get_metadata")}`);
    return res.ok;
  } catch {
    return false;
  }
}

function buildStudioInstructions() {
  const cq =
    financialSummary?.cashflow_quadrant ||
    architectDossier?.cashflow_quadrant ||
    architectDossier?.financial_summary?.cashflow_quadrant;
  const profileBlock = financialSummary
    ? `Financial profile (use real numbers in deliverables):\n${JSON.stringify(financialSummary, null, 2)}\n`
    : "";
  return (
    `STUDIO MODE — create deliverable files (not coaching). Hand off to Docs, Slides, Image, or Video specialist.\n` +
    `For standard financial reports, user can use /studio/reports/generate templates instead.\n` +
    `Save outputs under ./mnt/<project>/ and return download paths.\n` +
    `${profileBlock}${formatEsbiInstructions(cq)}`
  );
}

async function loadReportTemplates() {
  const grid = document.getElementById("report-templates");
  if (!grid) return;
  try {
    const data = await fetchJson("/studio/report-templates");
    grid.innerHTML = (data.templates || [])
      .map(
        (t) => `
      <article class="report-template-card">
        <h3>${escapeHtml(t.name)}</h3>
        <p class="small muted">${escapeHtml(t.description)}</p>
        <button type="button" class="btn btn-secondary btn-sm gen-report" data-id="${t.id}">Generate report</button>
      </article>`
      )
      .join("");
    grid.querySelectorAll(".gen-report").forEach((btn) => {
      btn.onclick = () => generateReport(btn.dataset.id, btn);
    });
  } catch {
    grid.innerHTML = '<p class="muted small">Templates load when server is running.</p>';
  }
}

async function loadPitchCardTemplates() {
  const grid = document.getElementById("pitch-card-templates");
  if (!grid) return;
  try {
    const data = await fetchJson("/studio/pitch-card-templates");
    grid.innerHTML = (data.templates || [])
      .map(
        (t) => `
      <article class="report-template-card">
        <h3>${escapeHtml(t.name)}</h3>
        <p class="small muted">${escapeHtml(t.description)}</p>
        <button type="button" class="btn btn-secondary btn-sm gen-pitch" data-id="${t.id}">Generate slide</button>
      </article>`
      )
      .join("");
    grid.querySelectorAll(".gen-pitch").forEach((btn) => {
      btn.onclick = () => generatePitchCard(btn.dataset.id, btn);
    });
  } catch {
    grid.innerHTML = '<p class="muted small">Pitch cards load when server is running.</p>';
  }
}

async function generatePitchCard(templateId, btn) {
  const statusEl = document.getElementById("pitch-gen-status");
  const label = btn?.textContent || "Generate";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Generating…";
  }
  statusEl.textContent = "";
  try {
    const result = await fetchJson("/studio/pitch-cards/generate", {
      method: "POST",
      body: JSON.stringify({ template_id: templateId, formats: ["html", "pdf"] }),
    });
    const links = (result.files || [])
      .map((f) => `<a href="${f.download_url}" target="_blank" rel="noopener">${f.format.toUpperCase()}</a>`)
      .join(" · ");
    statusEl.innerHTML = `Created <strong>${escapeHtml(result.document_name)}</strong> — ${links}`;
    const preview = pickPreviewFromResult(result);
    if (preview) {
      preview.name = `${result.document_name}.html`;
      await showPreview(preview);
    }
    await refreshArtifacts();
  } catch (e) {
    statusEl.textContent = e.message;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = label;
    }
  }
}

async function generateReport(templateId, btn) {
  const statusEl = document.getElementById("report-gen-status");
  const label = btn?.textContent || "Generate";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Generating…";
  }
  statusEl.textContent = "";
  try {
    const result = await fetchJson("/studio/reports/generate", {
      method: "POST",
      body: JSON.stringify({ template_id: templateId, formats: ["pdf", "html", "markdown"] }),
    });
    const links = (result.files || [])
      .map((f) => `<a href="${f.download_url}" target="_blank" rel="noopener">${f.format.toUpperCase()}</a>`)
      .join(" · ");
    statusEl.innerHTML = `Created <strong>${escapeHtml(result.document_name)}</strong> — ${links}`;
    const preview = pickPreviewFromResult(result);
    if (preview) {
      preview.name = result.document_name;
      await showPreview(preview);
    }
    await refreshArtifacts();
  } catch (e) {
    statusEl.textContent = e.message;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = label;
    }
  }
}

async function sendMessage(text) {
  appendMessage("user", text);
  document.getElementById("chat-input").value = "";
  appendMessage("assistant", "Working on it — routing to the right specialist…");

  const res = await fetch(AGENCY_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: text,
      recipient_agent: STUDIO_AGENT,
      additional_instructions: buildStudioInstructions(),
      user_context: {
        user_id: USER_ID,
        studio_mode: true,
        financial_summary: financialSummary,
        architect_dossier: architectDossier,
      },
      chat_history: chatHistory.length ? chatHistory : null,
    }),
  });

  const log = document.getElementById("chat-log");
  if (log.lastChild?.textContent?.startsWith("Working on it")) {
    log.removeChild(log.lastChild);
  }

  if (!res.ok) {
    const err = await res.text();
    appendMessage(
      "assistant",
      `Studio unavailable: ${err}. Run full server: python server.py (with OPENAI_API_KEY).`
    );
    return;
  }

  const data = await res.json();
  const reply = data.response || data.final_output || data.message || JSON.stringify(data);
  appendMessage("assistant", String(reply), { markdown: true });
  if (data.chat_history) {
    chatHistory = data.chat_history;
  } else if (Array.isArray(data.new_messages) && data.new_messages.length) {
    chatHistory = [...chatHistory, ...data.new_messages];
  }
  await refreshArtifacts();
}

document.getElementById("nav").innerHTML = renderNav("studio");

requireOnboarding().then(async () => {
  const statusEl = document.getElementById("studio-status");
  const available = await checkStudioAvailable();
  if (!available) {
    statusEl.textContent =
      "Studio requires the full server. Run: python server.py (with OPENAI_API_KEY).";
    statusEl.classList.remove("hidden");
  }

  try {
    architectDossier = await fetchJson(`/user/memory/dossier?user_id=${USER_ID}`);
  } catch {
    architectDossier = null;
  }

  try {
    financialSummary = await fetchJson("/user/intake/summary");
    const name = architectDossier?.architect_identity?.display_name || financialSummary.display_name;
    appendMessage(
      "assistant",
      `Studio ready, ${name}. I'll use your intake numbers in reports and decks when relevant. Pick a starter or describe what to create.`,
      { markdown: false }
    );
  } catch {
    appendMessage(
      "assistant",
      "Complete Financial Reality Intake for personalized reports and decks — or describe a generic deliverable to start.",
      { markdown: false }
    );
  }

  document.getElementById("refresh-artifacts").onclick = refreshArtifacts;
  document.getElementById("close-preview")?.addEventListener("click", closePreview);
  await loadReportTemplates();
  await loadPitchCardTemplates();
  await refreshArtifacts();

  const chips = document.getElementById("starter-chips");
  chips.innerHTML = STARTERS.map(
    (s) => `<button type="button" class="btn btn-secondary btn-sm starter">${s}</button>`
  ).join("");
  chips.querySelectorAll(".starter").forEach((btn) => {
    btn.onclick = () => sendMessage(btn.textContent);
  });

  document.getElementById("chat-form").onsubmit = (e) => {
    e.preventDefault();
    const text = document.getElementById("chat-input").value.trim();
    if (text) sendMessage(text);
  };
});
