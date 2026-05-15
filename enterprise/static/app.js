const api = {
  token: localStorage.getItem("enterprise_token"),
  headers() {
    return this.token ? { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
  },
  async request(path, options = {}) {
    const response = await fetch(path, { ...options, headers: { ...this.headers(), ...(options.headers || {}) } });
    if (response.status === 401 && location.pathname !== "/login") location.href = "/login";
    if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
    return response.json();
  }
};

async function login(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const data = await api.request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email: form.get("email"), password: form.get("password") })
  });
  localStorage.setItem("enterprise_token", data.access_token);
  location.href = "/dashboard";
}

function logout() {
  localStorage.removeItem("enterprise_token");
  location.href = "/login";
}

async function loadDashboard() {
  const [me, usage, runs] = await Promise.all([api.request("/api/me"), api.request("/api/usage"), api.request("/api/runs")]);
  document.querySelector("[data-me]").textContent = `${me.name} · ${me.role}`;
  document.querySelector("[data-runs]").textContent = usage.runs;
  document.querySelector("[data-completed]").textContent = usage.completed_runs;
  document.querySelector("[data-cost]").textContent = `$${(usage.estimated_cost_cents / 100).toFixed(2)}`;
  fillRuns(runs.slice(0, 8));
}

function fillRuns(runs) {
  const tbody = document.querySelector("[data-runs-table]");
  if (!tbody) return;
  tbody.innerHTML = runs.map(run => `<tr><td>${run.prompt.slice(0, 90)}</td><td><span class="badge">${run.state}</span></td><td>${new Date(run.created_at).toLocaleString()}</td><td>${run.result_summary || ""}</td></tr>`).join("");
}

async function loadRuns() {
  fillRuns(await api.request("/api/runs"));
}

async function createRun(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api.request("/api/runs", { method: "POST", body: JSON.stringify({ prompt: form.get("prompt"), auto_start: true }) });
  event.currentTarget.reset();
  await loadRuns();
}

async function loadAgents() {
  const agents = await api.request("/api/agents");
  const node = document.querySelector("[data-agents]");
  node.innerHTML = agents.map(agent => `<div class="card stat"><strong>${agent.name}</strong><p class="muted">${agent.description}</p><span class="badge">${agent.enabled ? "enabled" : "disabled"}</span></div>`).join("");
}

async function loadWorkspaces() {
  const workspaces = await api.request("/api/workspaces");
  const tbody = document.querySelector("[data-workspaces]");
  tbody.innerHTML = workspaces.map(item => `<tr><td>${item.name}</td><td>${item.description}</td><td>${new Date(item.created_at).toLocaleString()}</td></tr>`).join("");
}

async function createWorkspace(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api.request("/api/workspaces", { method: "POST", body: JSON.stringify({ name: form.get("name"), description: form.get("description") }) });
  event.currentTarget.reset();
  await loadWorkspaces();
}

async function loadAudit() {
  const events = await api.request("/api/audit");
  const tbody = document.querySelector("[data-audit]");
  tbody.innerHTML = events.map(event => `<tr><td>${new Date(event.created_at).toLocaleString()}</td><td>${event.action}</td><td>${event.resource_type}</td><td>${event.actor_id || ""}</td></tr>`).join("");
}

async function saveSecret(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api.request("/api/integrations/secrets", { method: "POST", body: JSON.stringify({ provider: form.get("provider"), value: form.get("value"), scope: form.get("scope") }) });
  event.currentTarget.reset();
  await loadSecrets();
}

async function loadSecrets() {
  const secrets = await api.request("/api/integrations/secrets");
  const tbody = document.querySelector("[data-secrets]");
  tbody.innerHTML = secrets.map(secret => `<tr><td>${secret.provider}</td><td>${secret.masked_value}</td><td>${secret.user_id ? "user" : "organization"}</td></tr>`).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-logout]").forEach(button => button.addEventListener("click", logout));
  const page = document.body.dataset.page;
  if (page === "dashboard") loadDashboard();
  if (page === "runs") loadRuns();
  if (page === "agents") loadAgents();
  if (page === "workspaces") loadWorkspaces();
  if (page === "audit") loadAudit();
  if (page === "integrations") loadSecrets();
});

