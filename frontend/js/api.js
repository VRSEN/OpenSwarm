// Same-origin when UI is served from the API (e.g. /static/...). Override with window.API_BASE if needed.
const API_BASE = window.API_BASE ?? "";

async function fetchJson(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function pillarBar(label, value, weight) {
  return `
    <div class="pillar">
      <div class="pillar-head">
        <span>${label}</span>
        <span>${value.toFixed(1)} <small>(${Math.round(weight * 100)}%)</small></span>
      </div>
      <div class="bar"><div class="fill" style="width:${value}%"></div></div>
    </div>`;
}

function tierClass(tier) {
  return `tier tier-${tier.toLowerCase()}`;
}

export { API_BASE, fetchJson, pillarBar, tierClass };
