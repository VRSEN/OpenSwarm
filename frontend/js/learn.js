import { fetchJson, requireOnboarding, renderNav, formatMoney } from "./app.js";

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function inlineMd(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function renderMdBlock(text) {
  return text
    .split("\n\n")
    .map((para) => {
      const trimmed = para.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("- ")) {
        const items = trimmed.split("\n").map((line) => `<li>${inlineMd(line.replace(/^-\s*/, ""))}</li>`);
        return `<ul class="lesson-list">${items.join("")}</ul>`;
      }
      return `<p>${inlineMd(trimmed).replace(/\n/g, "<br>")}</p>`;
    })
    .join("");
}

function profileLessonBox(module, summary) {
  if (!module.uses_profile || !summary) return "";
  const split = summary.allocation_156520 || {};
  const stab = summary.stability_fund || {};
  return `
    <div class="lesson-profile box">
      <strong>Your numbers (from intake)</strong>
      <div class="alloc-grid lesson-profile-grid">
        <div><span class="label">Income</span>${formatMoney(summary.monthly_gross_income)}</div>
        <div><span class="label">Essentials</span>${formatMoney(summary.monthly_essentials)}</div>
        <div><span class="label">Future 15%</span>${formatMoney(split.future)}</div>
        <div><span class="label">Stability Fund</span>${stab.pct_of_target ?? 0}% of target</div>
      </div>
    </div>`;
}

function buildLessonContent(module, summary) {
  const objectives = (module.objectives || [])
    .map((o) => `<li>${escapeHtml(o)}</li>`)
    .join("");
  const sections = (module.sections || [])
    .map(
      (s) =>
        `<h3 class="lesson-sub">${escapeHtml(s.title)}</h3><div class="lesson-section">${renderMdBlock(s.content || "")}</div>`
    )
    .join("");
  const example = module.worked_example
    ? `<div class="lesson-example"><h3 class="lesson-sub">Worked example</h3>${renderMdBlock(module.worked_example)}</div>`
    : "";
  const ex = module.exercise || {};
  const steps = (ex.steps || [])
    .map(
      (step, i) =>
        `<label class="checkbox exercise-step"><input type="checkbox" data-step="${i}" /> ${escapeHtml(step)}</label>`
    )
    .join("");
  const exercise = steps
    ? `<div class="lesson-exercise"><h3 class="lesson-sub">${escapeHtml(ex.title || "Exercise")}</h3>${steps}</div>`
    : "";
  const reflection = (module.reflection || [])
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");

  return `
    ${profileLessonBox(module, summary)}
    <div class="lesson-objectives"><h3 class="lesson-sub">You will learn to</h3><ul class="lesson-list">${objectives}</ul></div>
    ${sections}
    ${example}
    ${exercise}
    ${reflection ? `<div class="lesson-reflection"><h3 class="lesson-sub">Reflect (journal or discuss)</h3><ul class="lesson-list">${reflection}</ul></div>` : ""}
    <p class="key-point"><strong>Takeaway:</strong> ${escapeHtml(module.key_point || "")}</p>`;
}

function updateMarkButton(card) {
  const markBtn = card.querySelector(".mark-done");
  const boxes = card.querySelectorAll(".exercise-step input");
  if (!boxes.length) {
    markBtn.disabled = false;
    return;
  }
  const allChecked = [...boxes].every((b) => b.checked);
  markBtn.disabled = !allChecked;
  markBtn.title = allChecked ? "" : "Complete every exercise step first";
}

async function loadModules() {
  try {
    const data = await fetchJson("/user/literacy/modules");
    return data.modules;
  } catch {
    try {
      const data = await fetchJson("/literacy/modules");
      return data.modules;
    } catch {
      return [];
    }
  }
}

async function loadPlaybook(category = null, tag = null) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (tag) params.set("tag", tag);
  const q = params.toString() ? `?${params}` : "";
  try {
    return await fetchJson(`/user/literacy/playbook${q}`);
  } catch {
    return await fetchJson(`/literacy/playbook${q}`);
  }
}

const CATEGORY_LABELS = {
  mistake: "Mistake",
  strategy: "Strategy",
  mindset: "Mindset",
};

function renderPlaybook(entries) {
  const grid = document.getElementById("playbook-grid");
  if (!entries.length) {
    grid.innerHTML = '<p class="muted small">No playbook entries.</p>';
    return;
  }
    grid.innerHTML = entries
    .map(
      (e) => `
    <article class="playbook-card cat-${e.category}${(e.tags || []).includes("7-habits") ? " covey" : ""}${(e.tags || []).includes("esbi") ? " esbi" : ""}">
      <div class="playbook-card-head">
        <span class="playbook-cat">${CATEGORY_LABELS[e.category] || e.category}${(e.tags || []).includes("7-habits") ? " · 7 Habits" : ""}${(e.tags || []).includes("esbi") ? " · ESBI" : ""}</span>
        <h3>${escapeHtml(e.title)}</h3>
      </div>
      <p class="small"><strong>Idea:</strong> ${escapeHtml(e.key_concept)}</p>
      <p class="small"><strong>Do:</strong> ${escapeHtml(e.action)}</p>
      <p class="small muted"><strong>Impact:</strong> ${escapeHtml(e.impact)}</p>
      <p class="small playbook-app">${escapeHtml(e.app_link || "")}</p>
    </article>`
    )
    .join("");
}

async function initPlaybook() {
  const filtersEl = document.getElementById("playbook-filters");
  const buttons = [
    { cat: "", tag: "", label: "All" },
    { cat: "mistake", tag: "", label: "Mistakes" },
    { cat: "strategy", tag: "", label: "Strategies" },
    { cat: "mindset", tag: "", label: "Mindset" },
    { cat: "", tag: "7-habits", label: "7 Habits (Covey)" },
    { cat: "", tag: "esbi", label: "Cashflow Quadrant (ESBI)" },
  ];
  filtersEl.innerHTML = buttons
    .map(
      (b) =>
        `<button type="button" class="playbook-filter" data-cat="${b.cat}" data-tag="${b.tag}">${b.label}</button>`
    )
    .join("");

  const refresh = async (cat, tag) => {
    const data = await loadPlaybook(cat || null, tag || null);
    renderPlaybook(data.entries || []);
    filtersEl.querySelectorAll(".playbook-filter").forEach((btn) => {
      const active = btn.dataset.cat === (cat || "") && btn.dataset.tag === (tag || "");
      btn.classList.toggle("active", active);
    });
  };

  filtersEl.querySelectorAll(".playbook-filter").forEach((btn) => {
    btn.onclick = () => refresh(btn.dataset.cat || null, btn.dataset.tag || null);
  });

  await refresh(null, null);
}

document.getElementById("nav").innerHTML = renderNav("learn");

requireOnboarding().then(async (profile) => {
  if (!profile) return;
  try {
    await initPlaybook();

    const [modules, profileData, summary] = await Promise.all([
      loadModules(),
      fetchJson("/user/profile").catch(() => profile),
      fetchJson("/user/intake/summary").catch(() => null),
    ]);

    const done = new Set(profileData.literacy_completed || []);
    const list = document.getElementById("module-list");

    if (!modules.length) {
      list.innerHTML = '<p class="muted">No lessons available. Start the server with python server.py</p>';
      return;
    }

    list.innerHTML = modules
      .map(
        (m) => `
      <article class="card lesson-card" data-id="${m.id}">
        <div class="lesson-head">
          <h2>${m.order}. ${escapeHtml(m.title)}</h2>
          ${done.has(m.id) ? '<span class="badge">Completed</span>' : ""}
        </div>
        <p class="muted">${escapeHtml(m.summary || "")}</p>
        <div class="lesson-body hidden">${buildLessonContent(m, summary)}</div>
        <button type="button" class="btn btn-secondary expand-btn">Open lesson</button>
        <button type="button" class="btn mark-done hidden" disabled>Mark lesson complete</button>
      </article>`
      )
      .join("");

    list.querySelectorAll(".lesson-card").forEach((card) => {
      const expandBtn = card.querySelector(".expand-btn");
      const markBtn = card.querySelector(".mark-done");
      const moduleId = card.dataset.id;
      const alreadyDone = done.has(moduleId);

      expandBtn.onclick = () => {
        const body = card.querySelector(".lesson-body");
        const opening = body.classList.contains("hidden");
        body.classList.toggle("hidden");
        markBtn.classList.toggle("hidden", !opening);
        expandBtn.textContent = opening ? "Close lesson" : "Open lesson";
        if (opening && !alreadyDone) updateMarkButton(card);
      };

      card.querySelectorAll(".exercise-step input").forEach((box) => {
        box.onchange = () => updateMarkButton(card);
      });

      if (alreadyDone) {
        markBtn.classList.add("hidden");
        markBtn.disabled = false;
      }

      markBtn.onclick = async () => {
        if (markBtn.disabled) return;
        await fetchJson("/user/literacy/progress", {
          method: "POST",
          body: JSON.stringify({ module_id: moduleId, completed: true }),
        });
        if (!card.querySelector(".badge")) {
          card.querySelector(".lesson-head").insertAdjacentHTML(
            "beforeend",
            '<span class="badge">Completed</span>'
          );
        }
        markBtn.textContent = "Completed ✓";
        markBtn.disabled = true;
      };
    });
  } catch (e) {
    document.getElementById("error").textContent =
      e.message || "Could not load lessons. Run: python server.py";
  }
});
