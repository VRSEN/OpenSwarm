import { fetchJson, pillarBar, tierClass } from "./api.js";

const PILLAR_LABELS = {
  behavioral_trust: "Behavioral Trust",
  self_trust: "Self-Trust",
  pressure_performance: "Under Pressure",
  authenticity: "Authenticity / Quiet Builder",
  consistency: "Consistency / Invisible Years",
};

const WEIGHTS = {
  behavioral_trust: 0.25,
  self_trust: 0.2,
  pressure_performance: 0.2,
  authenticity: 0.2,
  consistency: 0.15,
};

async function loadReputation() {
  const data = await fetchJson("/reputation/score?consumer_tag_count=2&acquirer_tag_count=5");
  document.getElementById("composite").textContent = data.reputation_credit_score.toFixed(1);
  document.getElementById("tier").textContent = data.tier;
  document.getElementById("tier").className = tierClass(data.tier);
  document.getElementById("summary").textContent = data.travels_ahead_summary;
  document.getElementById("fund-gate").textContent = data.fund_now_eligible
    ? "Fund Now: eligible"
    : `Blocked: ${data.fund_now_block_reason || "requirements not met"}`;

  const pillarsEl = document.getElementById("pillars");
  pillarsEl.innerHTML = Object.entries(data.pillars)
    .map(([k, v]) => pillarBar(PILLAR_LABELS[k] || k, v, WEIGHTS[k] || 0.2))
    .join("");

  const unlocks = data.unlocks;
  document.getElementById("unlocks").innerHTML = `
    <li>Arbitrage funding: ${unlocks.arbitrage_funding ? "Yes" : "No"}</li>
    <li>Max fund: $${unlocks.max_fund_amount}</li>
    <li>CoC adjustment: ${unlocks.coc_adjustment_bps} bps</li>
    <li>Priority pipeline: ${unlocks.pipeline_priority ? "Yes" : "No"}</li>`;

  const selfTrust = await fetchJson("/reputation/self-trust");
  document.getElementById("self-trust-index").textContent = selfTrust.self_trust_index.toFixed(1);
}

loadReputation().catch((e) => {
  document.getElementById("error").textContent = `API error: ${e.message}. Start server with python server.py`;
});
