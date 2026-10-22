import { fetchJson, requireOnboarding, renderNav, renderAdvisorEsbiContext, formatEsbiInstructions } from "./app.js";

const AGENCY_PATH = "/Architect_Blueprint/get_response";
const USER_ID = "default";
const STARTERS = [
  "Build my debt payoff order",
  "How much should I set aside for taxes?",
  "Am I ready for a business line of credit?",
  "What's my next Stability-stage move?",
  "How do I move from S to B in my business?",
  "What does my ESBI income mix mean for my stage?",
];

let financialSummary = null;
let architectDossier = null;
let chatHistory = [];

function extractMessageText(msg) {
  if (!msg || typeof msg !== "object") return null;
  const role = msg.role;
  if (role !== "user" && role !== "assistant") return null;
  const content = msg.content;
  if (typeof content === "string") return content.trim() || null;
  if (Array.isArray(content)) {
    const parts = content
      .map((part) => part?.text || part?.input_text || part?.output_text || "")
      .filter(Boolean);
    return parts.join("\n").trim() || null;
  }
  return null;
}

function renderStoredChat(messages) {
  const log = document.getElementById("chat-log");
  log.innerHTML = "";
  for (const msg of messages) {
    const text = extractMessageText(msg);
    if (!text) continue;
    appendMessage(msg.role === "user" ? "user" : "assistant", text, {
      markdown: msg.role === "assistant",
    });
  }
}

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

    if (trimmed.startsWith("### ")) {
      closeList();
      out.push(`<h4>${inlineMarkdown(trimmed.slice(4))}</h4>`);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      closeList();
      out.push(`<h3>${inlineMarkdown(trimmed.slice(3))}</h3>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      closeList();
      out.push(`<h3>${inlineMarkdown(trimmed.slice(2))}</h3>`);
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

    const numberedMatch = trimmed.match(/^\d+\.\s+(.+)/);
    if (numberedMatch) {
      closeList();
      out.push(`<p class="chat-md-numbered">${inlineMarkdown(trimmed)}</p>`);
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

async function checkAdvisorAvailable() {
  try {
    const res = await fetch(`${AGENCY_PATH.replace("/get_response", "/get_metadata")}`);
    return res.ok;
  } catch {
    return false;
  }
}

async function sendMessage(text) {
  appendMessage("user", text);
  document.getElementById("chat-input").value = "";

  const cq =
    financialSummary?.cashflow_quadrant ||
    architectDossier?.cashflow_quadrant ||
    architectDossier?.financial_summary?.cashflow_quadrant;

  const contextBlock = financialSummary
    ? `User financial profile (use these numbers):\n${JSON.stringify(financialSummary, null, 2)}\n\n${formatEsbiInstructions(cq)}`
    : formatEsbiInstructions(cq) || "No financial profile loaded.";

  const res = await fetch(AGENCY_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: text,
      recipient_agent: "Architect Orchestrator",
      additional_instructions: contextBlock,
      user_context: {
        user_id: USER_ID,
        financial_summary: financialSummary,
        architect_dossier: architectDossier,
      },
      chat_history: chatHistory.length ? chatHistory : null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    appendMessage("assistant", `Advisor unavailable: ${err}. Run full server: python server.py (not run_mechanical.py only).`);
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
}

async function loadMemory() {
  try {
    architectDossier = await fetchJson(`/user/memory/dossier?user_id=${USER_ID}`);
    await fetchJson(`/user/memory/snapshots?user_id=${USER_ID}`, {
      method: "POST",
      body: JSON.stringify({ note: "Advisor session opened" }),
    });
  } catch {
    architectDossier = null;
  }

  try {
    const chat = await fetchJson(`/user/memory/chat?user_id=${USER_ID}`);
    if (chat.messages?.length) {
      chatHistory = chat.messages;
      renderStoredChat(chatHistory);
      return true;
    }
  } catch {
    /* no saved chat */
  }
  return false;
}

async function clearMemory() {
  if (!confirm("Clear advisor conversation history? Your intake profile and saved facts stay.")) return;
  await fetchJson(`/user/memory/chat?user_id=${USER_ID}`, { method: "DELETE" });
  chatHistory = [];
  document.getElementById("chat-log").innerHTML = "";
  appendMessage("assistant", "Conversation cleared. Your profile and remembered facts are still saved.");
}

document.getElementById("nav").innerHTML = renderNav("advisor");

requireOnboarding().then(async () => {
  const statusEl = document.getElementById("advisor-status");
  const available = await checkAdvisorAvailable();
  if (!available) {
    statusEl.textContent =
      "AI advisor requires the full server. Run: python server.py (with OPENAI_API_KEY). Mechanical-only mode has no chat.";
    statusEl.classList.remove("hidden");
  }

  const hadStoredChat = await loadMemory();

  try {
    financialSummary = await fetchJson("/user/intake/summary");
    const cq =
      financialSummary.cashflow_quadrant ||
      architectDossier?.cashflow_quadrant ||
      architectDossier?.financial_summary?.cashflow_quadrant;
    renderAdvisorEsbiContext(cq);

    if (!hadStoredChat) {
      const name = architectDossier?.architect_identity?.display_name || financialSummary.display_name;
      const stage = architectDossier?.journey?.stage || "Stability";
      const factCount = architectDossier?.remembered_facts?.length || 0;
      const esbiLine = cq
        ? ` Cashflow quadrant: ${cq.badge} (${cq.primary_label} → ${cq.target_label}).`
        : "";
      appendMessage(
        "assistant",
        `Welcome back, ${name}. Stage: ${stage}.${esbiLine} Income ${financialSummary.monthly_gross_income}, debt total ${financialSummary.debt_total}.` +
          (factCount ? ` I remember ${factCount} thing(s) from past conversations.` : "") +
          " Ask anything — I'll remember what matters and coach your ESBI path when relevant.",
        { markdown: false }
      );
    }
  } catch {
    if (!hadStoredChat) {
      appendMessage("assistant", "Complete Financial Reality Intake first for personalized answers.");
    }
  }

  document.getElementById("clear-chat")?.addEventListener("click", clearMemory);

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
