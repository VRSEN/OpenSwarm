import { fetchJson, requireOnboarding, renderNav, formatMoney, dataSourceBadge, renderEsbiPanel } from "./app.js?v=3";

function renderStartGuide(profile, journey, selfTrust) {
  const literacy = profile.literacy_completed || [];
  const lessonDone = literacy.length > 0;
  const hasCommitment = (selfTrust.active_commitments || []).length > 0;
  const hasCheckIn = (selfTrust.commitments_set || 0) > 0;

  const steps = [
    {
      done: profile.onboarding_completed,
      html: 'Complete <a href="/static/onboarding.html">Financial Reality Intake</a> — your income, debts, credit, business budget.',
    },
    {
      done: lessonDone,
      html: 'Open <a href="/static/learn.html">Learn</a> — complete lesson 1 (objectives + exercise checklist, not just a phrase).',
    },
    {
      done: hasCommitment,
      html: 'On <a href="/static/integrity.html">Your Integrity</a>, set one private promise (wake time, learning block, or pause rule).',
    },
    {
      done: hasCheckIn,
      html: "Weekly: check in Kept/Missed on that promise — that's what moves Self-Trust off 50.",
    },
    {
      done: false,
      html: `Stage: <strong>${journey.stage || "Stability"}</strong> — ${journey.next_mechanical_action || "fund Stability Fund."}`,
    },
    {
      done: false,
      html: 'Try <a href="/static/advisor.html">Ask Advisor</a> (AI chat — run <code>python server.py</code>, not mechanical-only).',
    },
  ];

  document.getElementById("start-steps").innerHTML = steps
    .map((s) => `<li class="${s.done ? "done" : ""}">${s.done ? "✓ " : ""}${s.html}</li>`)
    .join("");
}

function renderBreakdownList(items, labelKey, amountKey) {
  if (!items?.length) return "";
  return `<ul class="breakdown-list">${items
    .map(
      (x) =>
        `<li><span>${x[labelKey]}</span><strong>${formatMoney(x[amountKey])}</strong></li>`
    )
    .join("")}</ul>`;
}

function renderCreditPanel(summary) {
  const credit = summary.credit_plan || {};
  const snap = summary.credit_snapshot || {};
  const items = credit.collections_items || snap.collections_items || [];
  const flags = credit.flags || [];
  const actions = credit.weekly_actions || [];
  const hasCreditDetail =
    items.length ||
    flags.length ||
    actions.length ||
    credit.charge_offs ||
    credit.bankruptcies ||
    (credit.inquiries_6mo || 0) > 0 ||
    snap.total_credit_limit ||
    snap.estimated_score;

  const el = document.getElementById("reality-credit");
  if (!el) return;
  el.classList.toggle("hidden", !hasCreditDetail);

  const collectionsHtml = items.length
    ? `<ul class="breakdown-list">${items
        .map(
          (c) =>
            `<li><span>${c.creditor} <span class="muted small">(${c.status || "open"})</span></span><strong>${formatMoney(c.balance)}</strong></li>`
        )
        .join("")}</ul>`
    : "";

  const flagsHtml = flags.length
    ? `<ul class="credit-flags">${flags.map((f) => `<li>${f}</li>`).join("")}</ul>`
    : "";
  const actionsHtml = actions.length
    ? `<ul class="credit-actions">${actions.map((a) => `<li>${a}</li>`).join("")}</ul>`
    : "";

  el.innerHTML = `
    <h3 class="form-sub">Credit & collections</h3>
    <div class="credit-grid">
      <div><span class="label">Estimated score</span><strong>${snap.estimated_score || credit.estimated_score_midpoint || "—"}</strong></div>
      <div><span class="label">Utilization</span><strong>${credit.utilization_pct ?? snap.utilization_pct ?? 0}%</strong></div>
      <div><span class="label">Credit limits</span><strong>${formatMoney(snap.total_credit_limit || 0)}</strong></div>
      <div><span class="label">Revolving balance</span><strong>${formatMoney(snap.total_revolver_balance || 0)}</strong></div>
      <div><span class="label">Collections balance</span><strong>${formatMoney(credit.collections_balance || 0)}</strong></div>
      <div><span class="label">Charge-offs</span><strong>${credit.charge_offs ?? snap.charge_offs ?? 0}</strong></div>
      <div><span class="label">Bankruptcies</span><strong>${credit.bankruptcies ?? snap.bankruptcies ?? 0}</strong></div>
      <div><span class="label">Inquiries (6 mo)</span><strong>${credit.inquiries_6mo ?? snap.inquiries_6mo ?? 0}</strong></div>
    </div>
    ${collectionsHtml ? `<div class="breakdown-block"><h4 class="form-sub">Collection accounts</h4>${collectionsHtml}</div>` : ""}
    ${flagsHtml ? `<div class="breakdown-block"><h4 class="form-sub">Flags</h4>${flagsHtml}</div>` : ""}
    ${actionsHtml ? `<div class="breakdown-block"><h4 class="form-sub">This week</h4>${actionsHtml}</div>` : ""}`;
}

function renderFinancialReality(summary) {
  document.getElementById("data-badge").innerHTML = dataSourceBadge(summary.data_source);
  const income = summary.income_breakdown;
  const expense = summary.expense_breakdown;
  const incomeDetail = income?.streams?.length
    ? renderBreakdownList(
        income.streams.map((s) => ({ label: `${s.name} (${s.source_type})`, amount: s.amount_monthly })),
        "label",
        "amount"
      )
    : "";
  const expenseCats = expense?.by_category_labeled
    ? renderBreakdownList(
        Object.entries(expense.by_category_labeled).map(([label, amount]) => ({ label, amount })),
        "label",
        "amount"
      )
    : "";
  const billsDetail = expense?.bills?.length
    ? renderBreakdownList(expense.bills, "name", "amount_monthly")
    : "";

  document.dispatchEvent(new CustomEvent("reality:ready", { detail: summary }));
  document.getElementById("reality-grid").innerHTML = `
    <div><span class="label">Monthly income</span><strong>${formatMoney(summary.monthly_gross_income)}</strong></div>
    <div><span class="label">Monthly essentials</span><strong>${formatMoney(summary.monthly_essentials)}</strong></div>
    <div><span class="label">Debt total</span><strong>${formatMoney(summary.debt_total)}</strong></div>
    <div><span class="label">Stability Fund</span><strong>${summary.stability_fund.pct_of_target}%</strong></div>
    <div><span class="label">Credit band</span><strong>${summary.credit_plan.score_band}</strong></div>
    <div><span class="label">Loan readiness</span><strong>${summary.credit_plan.loan_readiness_score}/100</strong></div>`;

  const breakdownEl = document.getElementById("reality-breakdowns");
  if (breakdownEl) {
    const hasDetail = incomeDetail || expenseCats || billsDetail;
    breakdownEl.classList.toggle("hidden", !hasDetail);
    breakdownEl.innerHTML = hasDetail
      ? `
      ${incomeDetail ? `<div class="breakdown-block"><h3 class="form-sub">Income sources</h3>${incomeDetail}</div>` : ""}
      ${expenseCats ? `<div class="breakdown-block"><h3 class="form-sub">Expense categories</h3>${expenseCats}</div>` : ""}
      ${billsDetail ? `<div class="breakdown-block"><h3 class="form-sub">Recurring bills</h3>${billsDetail}</div>` : ""}`
      : "";
  }

  renderCreditPanel(summary);

  const snow = summary.debt_snowball;
  document.getElementById("snowball-line").textContent = snow.primary_target
    ? `Debt snowball #1: ${snow.primary_target} @ ${snow.guaranteed_return_pct}% APR — ${snow.rule}`
    : snow.message || "";
}

function renderQuickWins(data) {
  document.getElementById("quick-wins-list").innerHTML = (data.quick_wins || [])
    .map((w) => `<li><strong>${w.title}</strong> — ${w.action}</li>`)
    .join("");
  document.getElementById("opportunities-list").innerHTML = (data.opportunities || [])
    .map(
      (o) =>
        `<li class="${o.gated ? "muted" : ""}"><strong>${o.title}</strong>${o.gated ? " (locked)" : ""} — ${o.action}</li>`
    )
    .join("");
}

function formatMemoryDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return "";
  }
}

async function renderMemoryPanel() {
  const factsEl = document.getElementById("memory-facts");
  const emptyEl = document.getElementById("memory-empty");
  const summaryEl = document.getElementById("memory-summary");
  const snapshotsEl = document.getElementById("memory-snapshots");

  let dossier;
  let factsData;
  let chatData;
  let snapshotsData;

  try {
    [dossier, factsData, chatData, snapshotsData] = await Promise.all([
      fetchJson("/user/memory/dossier"),
      fetchJson("/user/memory/facts"),
      fetchJson("/user/memory/chat").catch(() => ({ count: 0 })),
      fetchJson("/user/memory/snapshots").catch(() => ({ snapshots: [] })),
    ]);
  } catch {
    summaryEl.innerHTML = `<p class="muted small">Memory loads when the full server is running (<code>python server.py</code>).</p>`;
    factsEl.innerHTML = "";
    snapshotsEl.innerHTML = "";
    emptyEl.classList.add("hidden");
    return;
  }

  const identity = dossier.architect_identity || {};
  const journey = dossier.journey || {};
  const cq = dossier.financial_summary?.cashflow_quadrant || journey.cashflow_quadrant;
  const facts = factsData.facts || [];
  const snapshots = snapshotsData.snapshots || [];

  summaryEl.innerHTML = `
    <div><span class="label">Architect</span><strong>${identity.display_name || "You"}</strong></div>
    <div><span class="label">Stage</span><strong>${journey.stage || "—"}</strong></div>
    ${cq ? `<div><span class="label">Cashflow quadrant</span><strong>${cq.badge || "—"}</strong></div>` : ""}
    <div><span class="label">Saved facts</span><strong>${facts.length}</strong></div>
    <div><span class="label">Chat messages</span><strong>${chatData.count ?? 0}</strong></div>`;

  if (!facts.length) {
    factsEl.innerHTML = "";
    emptyEl.classList.remove("hidden");
  } else {
    emptyEl.classList.add("hidden");
    factsEl.innerHTML = facts
      .map(
        (f) => `
      <li>
        <div class="memory-fact-body">
          <span class="memory-tag">${f.category || "general"}</span>
          ${f.content}
          <span class="small muted"> · ${formatMemoryDate(f.created_at)}${f.source_agent ? ` · ${f.source_agent}` : ""}</span>
        </div>
        <button type="button" class="btn btn-secondary btn-sm memory-forget" data-id="${f.id}">Forget</button>
      </li>`
      )
      .join("");

    factsEl.querySelectorAll(".memory-forget").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("Remove this remembered fact?")) return;
        await fetchJson(`/user/memory/facts/${btn.dataset.id}`, { method: "DELETE" });
        await renderMemoryPanel();
      };
    });
  }

  if (!snapshots.length) {
    snapshotsEl.innerHTML = `<li class="muted">No progress snapshots yet — open Ask Advisor to start tracking.</li>`;
  } else {
    snapshotsEl.innerHTML = snapshots
      .slice(0, 5)
      .map((s) => {
        const fund = s.metrics?.stability_fund_pct;
        const fundTxt = fund != null ? `${fund}% Stability Fund` : "";
        return `<li><strong>${s.stage}</strong> — ${formatMemoryDate(s.created_at)}${fundTxt ? ` · ${fundTxt}` : ""}${s.note ? `<br /><span class="small">${s.note}</span>` : ""}</li>`;
      })
      .join("");
  }
}

function verdictClass(verdict) {
  if (verdict === "BUY" || verdict === "TEST") return "verdict-go";
  if (verdict === "WAIT" || verdict === "ESCALATE") return "verdict-wait";
  return "verdict-stop";
}

function renderOmni(data) {
  const star = data.trajectory || {};
  const nw = data.net_worth || {};
  const alloc = data.allocation || {};
  document.getElementById("north-star-grid").innerHTML = `
    <div><span class="label">${star.label || "North Star"}</span><strong>${formatMoney(star.current_net_worth)}</strong> of ${formatMoney(star.target_net_worth)}</div>
    <div><span class="label">Pace</span><strong>${star.pct_of_target ?? 0}%</strong></div>
    <div><span class="label">Need / month</span><strong>${formatMoney(star.required_monthly_gain)}</strong></div>`;
  document.getElementById("net-worth-grid").innerHTML = `
    <div><span class="label">Assets</span><strong>${formatMoney(nw.assets?.total)}</strong></div>
    <div><span class="label">Debts</span><strong>${formatMoney(nw.liabilities?.total)}</strong></div>
    <div><span class="label">Net worth</span><strong>${formatMoney(nw.net_worth)}</strong></div>
    <div><span class="label">Baseline</span><strong>${nw.status || "—"}</strong></div>`;
  document.getElementById("risk-budget-line").textContent =
    `Risk budget (max loss this month): ${formatMoney(alloc.risk_budget)} · mode ${alloc.mode || "seed"} · ${alloc.rule || ""}`;
  const pct = Math.max(0, Math.min(100, Number(star.pct_of_target) || 0));
  const ring = document.getElementById("star-ring");
  if (ring) ring.style.setProperty("--pct", String(pct));
  const pctEl = document.getElementById("star-pct");
  if (pctEl) pctEl.textContent = `${Math.round(pct)}%`;
  document.dispatchEvent(new CustomEvent("omni:ready", { detail: { star, nw, alloc } }));

  const assets = nw.assets || {};
  const form = document.getElementById("wealth-state-form");
  if (form) {
    if (form.cash) form.cash.value = assets.cash ?? "";
    if (form.business_accounts) form.business_accounts.value = assets.business_accounts ?? "";
    if (form.productive_assets) form.productive_assets.value = assets.productive_assets ?? "";
    if (form.investments) form.investments.value = assets.investments ?? "";
  }

  const list = document.getElementById("smart-move-list");
  const moves = data.moves || [];
  if (!moves.length) {
    list.innerHTML = "<li class='muted'>No moves yet — underwrite an idea above.</li>";
  } else {
    list.innerHTML = moves
      .slice(0, 8)
      .map((m) => {
        const commitBtn =
          m.status === "underwritten" && ["BUY", "TEST", "ESCALATE"].includes(m.verdict)
            ? `<button type="button" class="btn btn-sm commit-move" data-id="${m.move_id}">I did it — commit</button>`
            : "";
        const closeBtn =
          m.status === "open"
            ? `<button type="button" class="btn btn-secondary btn-sm close-move" data-id="${m.move_id}">Close</button>`
            : "";
        return `<li><strong>${m.name}</strong> — <span class="${verdictClass(m.verdict)}">${m.verdict}</span> · ${m.status} · ${formatMoney(m.capital_required)} ${commitBtn} ${closeBtn}</li>`;
      })
      .join("");
  }
  list.querySelectorAll(".commit-move").forEach((btn) => {
    btn.onclick = () => commitMove(btn.dataset.id);
  });
  list.querySelectorAll(".close-move").forEach((btn) => {
    btn.onclick = () => closeMove(btn.dataset.id);
  });
}

function showUnderwrite(packet) {
  const el = document.getElementById("smart-move-result");
  el.classList.remove("hidden");
  const playbook = (packet.playbook || []).map((s) => `<li>${s.action}</li>`).join("");
  const kill = (packet.kill_case?.reasons || []).map((r) => `<li>${r}</li>`).join("");
  el.innerHTML = `
    <p><strong class="${verdictClass(packet.verdict)}">${packet.verdict}</strong> — ${packet.name}</p>
    <p class="small">Max loss ${formatMoney(packet.assurance?.max_loss)} vs budget ${formatMoney(packet.assurance?.risk_budget)}. Stability Fund stays untouched.</p>
    <p class="small"><strong>Kill case:</strong></p>
    <ul class="credit-flags">${kill}</ul>
    <p class="small"><strong>If you proceed, do this (you click the buttons on the platform — we don't):</strong></p>
    <ol class="guide-steps">${playbook}</ol>
    <p class="muted small">${packet.disclaimer}</p>`;
}

async function loadOmniWealth() {
  const data = await fetchJson("/wealth/command");
  renderOmni(data);
}

async function commitMove(moveId) {
  if (!confirm("Confirm you accept the max loss and already (or will immediately) follow the playbook. This does not send money.")) return;
  await fetchJson("/wealth/moves/commit", {
    method: "POST",
    body: JSON.stringify({ move_id: moveId, confirm_max_loss: true }),
  });
  await loadOmniWealth();
}

async function closeMove(moveId) {
  await fetchJson("/wealth/moves/close", {
    method: "POST",
    body: JSON.stringify({ move_id: moveId, result: "closed" }),
  });
  await loadOmniWealth();
}

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const meter = (part, whole) => `<div class="meter"><i style="width:${whole ? Math.min(100, (part / whole) * 100) : 0}%"></i></div>`;
const STATUS_WORD = { now: "Use now", next: "Next unlock", later: "Later", check: "Check first" };

function renderToday(data) {
  const month = data.month || {};
  const target = data.month_target || {};
  const tax = data.tax || {};
  document.getElementById("today-date").textContent = data.date || "";
  document.getElementById("month-strip").innerHTML = `
    <div><span>In this month</span><strong>${formatMoney(month.in)}</strong><em>of ${formatMoney(target.income)} expected</em>${meter(month.in, target.income)}</div>
    <div><span>Bills covered</span><strong>${formatMoney(month.essentials)}</strong><em>of ${formatMoney(target.essentials)}</em>${meter(month.essentials, target.essentials)}</div>
    <div><span>Bet budget left</span><strong>${formatMoney(data.risk?.left)}</strong><em>of ${formatMoney(data.risk?.budget)} this month</em>${meter(data.risk?.left, data.risk?.budget)}</div>
    <div><span>Tax set aside</span><strong>${formatMoney(month.tax)}</strong><em>${tax.pct ?? 0}% · ${esc(tax.next?.label)} due ${esc(tax.next?.due)} (${tax.next?.days_left ?? "?"}d)</em></div>`;

  const list = document.getElementById("route-list");
  const open = data.open_routes || [];
  document.getElementById("routes-head").textContent = open.length
    ? `Moves waiting on you · ${open.length}`
    : "Moves waiting on you";
  list.innerHTML = open.length
    ? open
        .map(
          (r) => `<li class="route-${r.key}">
            <div><b>${esc(r.label)}</b><span class="route-dest">→ ${esc(r.destination)}</span><span class="route-why">${esc(r.why)} · from ${esc(r.source)} (${esc(r.date)})</span></div>
            <span class="route-amt">${formatMoney(r.amount)}</span>
            <button type="button" class="btn btn-sm route-done" data-id="${esc(r.inflow_id)}" data-key="${esc(r.key)}">Moved it</button>
          </li>`
        )
        .join("")
    : `<li class="route-empty">Nothing waiting. When money lands, type the amount above and hit Route it.</li>`;
  list.querySelectorAll(".route-done").forEach((btn) => {
    btn.onclick = () => markRouteDone(btn);
  });

  const tools = data.toolbox || [];
  document.getElementById("toolbox-date").textContent = tools[0]?.researched_on ? `on ${tools[0].researched_on}` : "";
  const order = { now: 0, next: 1, check: 2, later: 3 };
  document.getElementById("toolbox-grid").innerHTML = [...tools]
    .sort((a, b) => order[a.status] - order[b.status])
    .map(
      (t) => `<article class="tool status-${t.status}">
        <span class="chip chip-${t.status}">${STATUS_WORD[t.status] || t.status}</span>
        <h3>${esc(t.name)}</h3>
        <p>${esc(t.what)}</p>
        <p class="tool-limit">${esc(t.limit)}</p>
        <p class="tool-use">${esc(t.status === "now" || !t.gate ? t.use_for : t.gate)}</p>
        <a href="${esc(t.source)}" target="_blank" rel="noopener">Source ↗</a>
      </article>`
    )
    .join("");
}

async function loadToday() {
  renderToday(await fetchJson("/wealth/today"));
}

async function markRouteDone(btn) {
  btn.disabled = true;
  const res = await fetchJson("/wealth/inflow/done", {
    method: "POST",
    body: JSON.stringify({ inflow_id: btn.dataset.id, key: btn.dataset.key }),
  });
  renderToday(res.today);
  if (["fund", "invest"].includes(btn.dataset.key)) await loadOmniWealth();
}

function showDeck(name) {
  document.body.dataset.view = name;
  document.querySelectorAll("[data-deck]").forEach((el) => {
    if (el.classList.contains("deck-btn")) return;
    el.classList.toggle("deck-hidden", el.dataset.deck !== name);
  });
  document.querySelectorAll(".deck-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.deck === name);
  });
}

document.querySelectorAll(".deck-btn").forEach((btn) => {
  btn.addEventListener("click", () => showDeck(btn.dataset.deck));
});
showDeck("pulse");

document.getElementById("nav").innerHTML = renderNav("home");

function applySolitudeMode(active) {
  const on = active === true;
  document.getElementById("main-standard").classList.toggle("hidden", on);
  document.getElementById("main-solitude").classList.toggle("hidden", !on);
  document.body.classList.toggle("solitude-mode", on);
  document.getElementById("nav").classList.toggle("hidden", on);
}

const EMOTIONS = [
  ["stress", "Stress"],
  ["boredom", "Boredom"],
  ["status", "Status"],
  ["social", "Social"],
  ["comfort", "Comfort"],
];

async function loadForkMoments() {
  const data = await fetchJson("/mirror/fork-moments");
  const el = document.getElementById("active-pauses");
  const clearBtn = document.getElementById("clear-unlocked-pauses");
  const pauses = data.active_pauses || [];
  const unlockedCount = pauses.filter((p) => p.unlocked).length;
  if (clearBtn) clearBtn.classList.toggle("hidden", unlockedCount === 0);

  if (!pauses.length) {
    el.innerHTML = '<p class="muted small">No active pauses. Add a want-to-buy item below if you need a cooling-off period.</p>';
    return;
  }
  el.innerHTML = pauses
    .map((p) => {
      const hours = Math.round(p.hours_remaining);
      const timer = p.unlocked ? "Pause complete — you can decide now" : `${hours}h left`;
      const emotions = !p.emotion_acknowledged
        ? `<p class="muted small">What is driving this?</p>
           <div class="emotion-btns">${EMOTIONS.map(
             ([id, label]) =>
               `<button type="button" class="ack-emotion" data-id="${p.id}" data-emotion="${id}">${label}</button>`
           ).join("")}</div>`
        : `<p class="identity small">${p.identity_notification || "Feeling noted. Let the clock finish."}</p>`;
      return `
    <div class="pause-card">
      <strong>${p.item}</strong> — ${formatMoney(p.amount)}
      <span class="small muted">${timer}</span>
      ${emotions}
      <button type="button" class="btn btn-secondary btn-sm dismiss-pause" data-id="${p.id}">Dismiss</button>
    </div>`;
    })
    .join("");

  el.querySelectorAll(".ack-emotion").forEach((btn) => {
    btn.onclick = () => acknowledgePause(Number(btn.dataset.id), btn.dataset.emotion);
  });
  el.querySelectorAll(".dismiss-pause").forEach((btn) => {
    btn.onclick = () => releasePause(Number(btn.dataset.id));
  });
}

async function acknowledgePause(pauseId, emotion) {
  const res = await fetchJson("/mirror/fork-moments/acknowledge", {
    method: "POST",
    body: JSON.stringify({
      pause_id: pauseId,
      emotion,
      choose_architect_path: true,
    }),
  });
  document.getElementById("identity-line").textContent = res.identity_notification;
  await loadForkMoments();
}

async function releasePause(pauseId, releaseAllUnlocked = false) {
  await fetchJson("/mirror/fork-moments/release", {
    method: "POST",
    body: JSON.stringify(
      releaseAllUnlocked ? { release_all_unlocked: true } : { pause_id: pauseId }
    ),
  });
  await loadForkMoments();
}

requireOnboarding().then(async (profile) => {
  if (!profile) return;

  const welcome = sessionStorage.getItem("welcome_message");
  if (welcome) {
    document.getElementById("welcome-banner").textContent = welcome;
    document.getElementById("welcome-banner").classList.remove("hidden");
    sessionStorage.removeItem("welcome_message");
  }

  document.getElementById("greeting").textContent = "Command";
  document.getElementById("focus-toggle").checked = profile.solitude_mode_active;
  document.getElementById("creation-hour").value = profile.creation_hour || "07:00";
  applySolitudeMode(profile.solitude_mode_active);

  document.getElementById("focus-save").onclick = async () => {
    const res = await fetchJson("/user/focus-season", {
      method: "POST",
      body: JSON.stringify({
        active: document.getElementById("focus-toggle").checked,
        creation_hour: document.getElementById("creation-hour").value,
      }),
    });
    document.getElementById("focus-msg").textContent = res.identity_notification;
    applySolitudeMode(res.solitude_mode_active);
  };

  document.getElementById("fork-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const res = await fetchJson("/mirror/fork-moments/pause", {
      method: "POST",
      body: JSON.stringify({
        item_description: fd.get("item"),
        amount: Number(fd.get("amount")),
        bucket: "life",
      }),
    });
    if (res.status === "paused") {
      e.target.reset();
      await loadForkMoments();
    }
  };

  document.getElementById("clear-unlocked-pauses")?.addEventListener("click", () => {
    releasePause(null, true);
  });

  document.getElementById("wealth-state-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = {};
    for (const [k, v] of fd.entries()) {
      if (v !== "") body[k] = Number(v);
    }
    const data = await fetchJson("/wealth/state", { method: "POST", body: JSON.stringify(body) });
    renderOmni(data);
  });

  document.getElementById("smart-move-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = {
      name: fd.get("name"),
      move_type: fd.get("move_type"),
      platform: fd.get("platform") || "",
      capital_required: Number(fd.get("capital_required") || 0),
      expected_profit: Number(fd.get("expected_profit") || 0),
      recycle_days: Number(fd.get("recycle_days") || 14),
      exit_plan: fd.get("exit_plan") || "",
    };
    const maxLoss = fd.get("max_loss");
    if (maxLoss) body.max_loss = Number(maxLoss);
    const packet = await fetchJson("/wealth/moves/underwrite", {
      method: "POST",
      body: JSON.stringify(body),
    });
    showUnderwrite(packet);
    await loadOmniWealth();
  });

  document.getElementById("inflow-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const res = await fetchJson("/wealth/inflow", {
      method: "POST",
      body: JSON.stringify({
        amount: Number(fd.get("amount")),
        source: fd.get("source") || "",
        kind: fd.get("kind") || "business",
      }),
    });
    e.target.reset();
    renderToday(res.today);
  });

  document.getElementById("reset-profile").onclick = async () => {
    if (!confirm("Clear all your data and start intake again?")) return;
    await fetchJson("/user/intake/reset", { method: "POST" });
    window.location.href = "/static/get-started.html";
  };

  try {
    const summary = await fetchJson("/user/intake/summary");
    renderFinancialReality(summary);

    const missions = await fetchJson("/mirror/dollar-missions");
    document.getElementById("gap-message").textContent = missions.gap_message;
    document.getElementById("missions-list").innerHTML = missions.missions
      .map(
        (m) =>
          `<li><strong>${m.job}</strong> — ${formatMoney(m.amount)} <span class="muted">(${m.rule})</span></li>`
      )
      .join("");

    const journey = await fetchJson("/user/journey");
    document.getElementById("stage-name").textContent = journey.stage;
    document.getElementById("stage-progress").style.width = `${(journey.stage_index / journey.total_stages) * 100}%`;
    document.getElementById("next-action").textContent = journey.next_mechanical_action;
    renderEsbiPanel(journey.cashflow_quadrant);

    const selfTrust = await fetchJson("/reputation/self-trust");
    renderStartGuide(profile, journey, selfTrust);

    const quickWins = await fetchJson("/user/intake/quick-wins");
    renderQuickWins(quickWins);

    await renderMemoryPanel();

    await loadForkMoments();
    try {
      await loadOmniWealth();
      await loadToday();
    } catch {
      /* OmniWealth panel fills after intake exists */
    }

    try {
      const fundPct = Number(journey.stability_fund_pct || 0);
      const mirror = await fetchJson(`/dashboard/mirror?stability_fund_pct=${fundPct}`);
      document.getElementById("identity-line").textContent ||= mirror.identity_line;
      document.getElementById("solitude-integrity").textContent = mirror.silent_kpis.reputation_credit_score.toFixed(0);
      document.getElementById("deep-work").textContent = profile.creation_hour || "—";
    } catch {
      document.getElementById("deep-work").textContent = profile.creation_hour || "—";
    }
  } catch (e) {
    document.getElementById("error").textContent = e.message;
  }
});
