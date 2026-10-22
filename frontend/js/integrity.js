import { fetchJson, pillarBar, requireOnboarding, renderNav, tierClass } from "./app.js";

const PILLAR_LABELS = {
  behavioral_trust: "Follow-through",
  self_trust: "Self-Trust",
  pressure_performance: "Under pressure",
  authenticity: "Quiet builder",
  consistency: "Consistency",
};

const BASELINE_PILLARS = new Set(["behavioral_trust", "self_trust", "consistency"]);

document.getElementById("nav").innerHTML = renderNav("integrity");

function renderScores(data) {
  document.getElementById("composite").textContent = data.reputation_credit_score.toFixed(1);
  document.getElementById("tier").textContent = data.tier;
  document.getElementById("tier").className = tierClass(data.tier);
  document.getElementById("summary").textContent = data.travels_ahead_summary;

  const detail = data.self_trust_detail || {};
  const isDayZero = (detail.commitments_set || 0) === 0;

  document.getElementById("pillars").innerHTML = Object.entries(data.pillars)
    .map(([k, v]) => {
      const baseline =
        isDayZero && BASELINE_PILLARS.has(k) && Math.abs(v - 50) < 0.1
          ? ' <span class="baseline-tag">starting line</span>'
          : "";
      return pillarBar((PILLAR_LABELS[k] || k) + baseline, v, 0.2);
    })
    .join("");

  return { isDayZero, detail };
}

function renderDayZeroGuide(isDayZero, detail, commitmentCount) {
  const guide = document.getElementById("day-zero-guide");
  guide.classList.remove("hidden");

  document.getElementById("guide-intro").textContent = isDayZero
    ? "You are at the starting line—not failing. Most pillars default to 50 until you log real behavior. Bronze (~58) is just math on those defaults plus a few formula bonuses (e.g. Under pressure starts at 70 when no crisis data exists)."
    : "Your score is updating from logged behavior. Keep weekly check-ins and use Fork Moments when tempted to spend.";

  document.getElementById("score-sources").innerHTML = [
    "<strong>Follow-through, Self-Trust, Consistency at ~50</strong> — no delivery history or check-ins yet.",
    "<strong>Under pressure at ~70</strong> — neutral default (no stress-test events recorded).",
    "<strong>Quiet builder ~71</strong> — formula default, not proof you are already reinvesting.",
    "<strong>RARITY at 100</strong> — placeholder skill/discipline inputs until Learn + real habits feed the engine.",
    "<strong>Command Center dollars</strong> — from onboarding demo footprints until a real bank connection replaces them.",
  ]
    .map((line) => `<li>${line}</li>`)
    .join("");

  const checkInDone = (detail.commitments_set || 0) > 0;
  document.getElementById("guide-steps").innerHTML = [
    { done: true, html: 'Finish <a href="/static/onboarding.html">Clinical Life Audit</a> (if you have not).' },
    { done: commitmentCount > 0, html: "Set one private commitment below (wake time, learning block, or 72h pause rule)." },
    { done: checkInDone, html: "Each week: tap <strong>Kept it</strong> or <strong>Missed</strong> — Self-Trust moves off 50." },
    { done: false, html: 'Read lesson 1 on <a href="/static/learn.html">Learn</a> — cash flow machine (15/65/20).' },
    { done: false, html: "On Command Center: follow Dollar Missions and use Fork Moments before non-essential buys." },
  ]
    .map(
      (s) =>
        `<li class="${s.done ? "done" : ""}">${s.done ? "✓ " : ""}${s.html}</li>`
    )
    .join("");
}

function renderCommitments(commitments, onCheckIn) {
  const el = document.getElementById("active-commitments");
  if (!commitments.length) {
    el.innerHTML =
      '<p class="muted small">No active commitments yet. Save one above, then check in weekly.</p>';
    return;
  }

  el.innerHTML = commitments
    .map(
      (c) => `
    <div class="commitment-row" data-id="${c.id}">
      <div class="commitment-meta">
        <strong>${c.description}</strong>
        ${c.target_value ? `<span class="muted small"> — ${c.target_value}</span>` : ""}
        <div class="muted small">Streak: ${c.streak_days || 0} day(s)</div>
      </div>
      <div class="commitment-actions">
        <button type="button" class="btn btn-sm btn-kept" data-kept="true">Kept it</button>
        <button type="button" class="btn btn-sm btn-missed" data-kept="false">Missed</button>
      </div>
    </div>`
    )
    .join("");

  el.querySelectorAll("button[data-kept]").forEach((btn) => {
    btn.onclick = () => {
      const row = btn.closest(".commitment-row");
      onCheckIn(Number(row.dataset.id), btn.dataset.kept === "true");
    };
  });
}

async function refreshAll() {
  const data = await fetchJson("/reputation/score");
  const { isDayZero, detail } = renderScores(data);

  const selfTrust = await fetchJson("/reputation/self-trust");
  document.getElementById("self-trust-index").textContent =
    selfTrust.self_trust_index.toFixed(1);

  renderDayZeroGuide(isDayZero, detail, (selfTrust.active_commitments || []).length);
  renderCommitments(selfTrust.active_commitments || [], async (commitmentId, kept) => {
    const result = await fetchJson("/reputation/self-trust/check-in", {
      method: "POST",
      body: JSON.stringify({
        commitment_id: commitmentId,
        kept_commitment: kept,
        event_type: kept ? "check_in" : "pause_broken",
      }),
    });
    document.getElementById("check-in-msg").textContent = kept
      ? `Logged. Self-Trust is now ${result.self_trust_index.toFixed(1)}.`
      : `Logged honestly. Self-Trust is ${result.self_trust_index.toFixed(1)}—adjust the promise or try again.`;
    await refreshAll();
  });
}

requireOnboarding().then(async () => {
  try {
    await refreshAll();

    document.getElementById("commit-form").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      await fetchJson("/reputation/self-commitments", {
        method: "POST",
        body: JSON.stringify({
          benchmark_type: fd.get("benchmark_type"),
          description: fd.get("description"),
          target_value: fd.get("target_value"),
        }),
      });
      e.target.reset();
      document.getElementById("commit-msg").textContent =
        "Commitment saved. Check in below when the week ends—or daily for rhythm habits.";
      await refreshAll();
    };
  } catch (e) {
    document.getElementById("error").textContent = e.message;
  }
});
