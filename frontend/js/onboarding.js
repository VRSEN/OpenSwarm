import { fetchJson } from "./app.js";

const EDIT_MODE = new URLSearchParams(location.search).get("edit") === "1";
let totalSteps = EDIT_MODE ? 8 : 9;

const EXPENSE_FIELDS = [
  { key: "housing", label: "Housing (rent / mortgage)" },
  { key: "utilities", label: "Utilities & phone" },
  { key: "food_groceries", label: "Food & groceries" },
  { key: "transportation", label: "Transportation & gas" },
  { key: "insurance", label: "Insurance (non-health)" },
  { key: "healthcare", label: "Healthcare & meds" },
  { key: "childcare", label: "Childcare & dependents" },
  { key: "personal", label: "Personal / household" },
  { key: "business_opex", label: "Business costs (personal account)" },
  { key: "debt_minimums", label: "Debt minimum payments" },
  { key: "other", label: "Other essentials" },
];

let step = 1;
const incomeStreams = [];
const bills = [];
const debts = [];
const collections = [];
const footprints = { banking: false, calendar: false, screen_time: false };

function showStep() {
  for (let i = 1; i <= 9; i++) {
    document.getElementById(`step-${i}`)?.classList.toggle("hidden", i !== step);
  }
  document.getElementById("step-label").textContent = `Step ${step} of ${totalSteps}`;
  document.getElementById("btn-back").classList.toggle("hidden", step === 1);
  document.getElementById("btn-next").textContent =
    step === totalSteps ? (EDIT_MODE ? "Save & return" : "Begin as Architect") : "Save & continue";
  updateTotals();
}

function money(n) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n || 0);
}

function updateTotals() {
  const incomeTotal = incomeStreams.reduce((s, x) => s + Number(x.amount_monthly || 0), 0);
  const el = document.getElementById("income-total");
  if (el) el.textContent = money(incomeTotal);

  let expenseTotal = 0;
  EXPENSE_FIELDS.forEach(({ key }) => {
    const input = document.querySelector(`[name="exp_${key}"]`);
    if (input) expenseTotal += Number(input.value || 0);
  });
  expenseTotal += bills.reduce((s, b) => s + Number(b.amount_monthly || 0), 0);
  const expEl = document.getElementById("expense-total");
  if (expEl) expEl.textContent = money(expenseTotal);
}

function renderList(containerId, items, renderItem, emptyMsg) {
  const el = document.getElementById(containerId);
  if (!items.length) {
    el.innerHTML = `<p class="muted small">${emptyMsg}</p>`;
    return;
  }
  el.innerHTML = items.map(renderItem).join("");
}

function renderIncomeStreams() {
  renderList(
    "income-list",
    incomeStreams,
    (d, i) => `
    <div class="line-item">
      <strong>${d.name}</strong> — ${money(d.amount_monthly)}/mo <span class="muted small">(${d.source_type})</span>
      <button type="button" class="btn btn-secondary btn-sm remove-income" data-idx="${i}">Remove</button>
    </div>`,
    "Add each income source — W-2, business deposits, passive, gigs."
  );
  document.querySelectorAll(".remove-income").forEach((btn) => {
    btn.onclick = () => {
      incomeStreams.splice(Number(btn.dataset.idx), 1);
      renderIncomeStreams();
      updateTotals();
    };
  });
}

function renderBills() {
  renderList(
    "bill-list",
    bills,
    (b, i) => `
    <div class="line-item">
      <strong>${b.name}</strong> — ${money(b.amount_monthly)}/mo ${b.due_day ? `(due day ${b.due_day})` : ""}
      ${b.autopay ? '<span class="muted small"> · autopay</span>' : ""}
      <button type="button" class="btn btn-secondary btn-sm remove-bill" data-idx="${i}">Remove</button>
    </div>`,
    "Add recurring bills — subscriptions, utilities, loan autopays."
  );
  document.querySelectorAll(".remove-bill").forEach((btn) => {
    btn.onclick = () => {
      bills.splice(Number(btn.dataset.idx), 1);
      renderBills();
      updateTotals();
    };
  });
}

function renderDebts() {
  renderList(
    "debt-list",
    debts,
    (d, i) => `
    <div class="line-item">
      <strong>${d.name}</strong> — ${money(d.balance)} @ ${d.apr}% APR (min ${money(d.minimum_payment)})
      ${d.in_collections ? '<span class="tag-warn">collections</span>' : ""}
      <button type="button" class="btn btn-secondary btn-sm remove-debt" data-idx="${i}">Remove</button>
    </div>`,
    "No debts added — click Add debt or continue if debt-free."
  );
  document.querySelectorAll(".remove-debt").forEach((btn) => {
    btn.onclick = () => {
      debts.splice(Number(btn.dataset.idx), 1);
      renderDebts();
    };
  });
}

function renderCollections() {
  renderList(
    "collection-list",
    collections,
    (c, i) => `
    <div class="line-item">
      <strong>${c.creditor}</strong> — ${money(c.balance)} <span class="muted small">(${c.status})</span>
      <button type="button" class="btn btn-secondary btn-sm remove-collection" data-idx="${i}">Remove</button>
    </div>`,
    "Add each collection account separately if applicable."
  );
  document.querySelectorAll(".remove-collection").forEach((btn) => {
    btn.onclick = () => {
      collections.splice(Number(btn.dataset.idx), 1);
      renderCollections();
    };
  });
}

function readInlineForm(prefix) {
  const g = (name) => document.getElementById(`${prefix}-${name}`)?.value?.trim() ?? "";
  const gn = (name) => Number(document.getElementById(`${prefix}-${name}`)?.value || 0);
  return { g, gn };
}

document.getElementById("add-income")?.addEventListener("click", () => {
  const { g, gn } = readInlineForm("income");
  const name = g("name");
  if (!name) return alert("Enter income source name.");
  incomeStreams.push({
    name,
    source_type: g("type") || "business",
    amount_monthly: gn("amount"),
    frequency: "monthly",
    notes: g("notes"),
  });
  ["name", "amount", "notes"].forEach((f) => {
    const el = document.getElementById(`income-${f}`);
    if (el) el.value = f === "amount" ? "0" : "";
  });
  renderIncomeStreams();
  updateTotals();
});

document.getElementById("add-bill")?.addEventListener("click", () => {
  const { g, gn } = readInlineForm("bill");
  const name = g("name");
  if (!name) return alert("Enter bill name.");
  bills.push({
    name,
    amount_monthly: gn("amount"),
    due_day: gn("due"),
    category: g("category") || "other",
    autopay: document.getElementById("bill-autopay")?.checked || false,
  });
  renderBills();
  updateTotals();
});

document.getElementById("add-debt")?.addEventListener("click", () => {
  const { g, gn } = readInlineForm("debt");
  const name = g("name");
  if (!name) return alert("Enter debt name.");
  debts.push({
    name,
    balance: gn("balance"),
    apr: gn("apr"),
    minimum_payment: gn("min"),
    secured: document.getElementById("debt-secured")?.checked || false,
    debt_type: g("type") || "other",
    past_due_amount: gn("pastdue"),
    in_collections: document.getElementById("debt-collections")?.checked || false,
  });
  renderDebts();
});

document.getElementById("add-collection")?.addEventListener("click", () => {
  const { g, gn } = readInlineForm("coll");
  const creditor = g("creditor");
  if (!creditor) return alert("Enter creditor name.");
  collections.push({
    creditor,
    balance: gn("balance"),
    status: g("status") || "open",
    notes: g("notes"),
  });
  renderCollections();
});

document.querySelectorAll(".connect-btn").forEach((btn) => {
  btn.onclick = () => {
    const source = btn.dataset.source;
    footprints[source] = !footprints[source];
    btn.classList.toggle("connected", footprints[source]);
    const active = Object.entries(footprints)
      .filter(([, v]) => v)
      .map(([k]) => k.replace("_", " "))
      .join(", ");
    document.getElementById("connect-status").textContent = active
      ? `Optional footprints: ${active}`
      : "Skip or connect demo footprints for behavioral patterns.";
  };
});

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function saveStep(n, body) {
  const res = await fetchJson(`/user/intake/step/${n}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (res.preview) {
    const p = res.preview;
    document.getElementById("preview-box").classList.remove("hidden");
    document.getElementById("preview-box").innerHTML = `
      <strong>Preview:</strong> Income ${money(p.monthly_gross_income)} · Expenses ${money(p.monthly_essentials)} ·
      15/65/20 Future ${money(p.allocation_156520?.future)} · Stability ${p.stability_fund?.pct_of_target ?? 0}%
      ${p.debt_snowball?.primary_target ? ` · Snowball: ${p.debt_snowball.primary_target}` : ""}`;
  }
  return res;
}

function syncQuadrantFromEmployment() {
  const emp = document.getElementById("employment-type")?.value || "self_employed";
  const quad = document.getElementById("cashflow-quadrant");
  if (!quad) return;
  const map = { self_employed: "S", business_owner: "B", side_hustle: "S" };
  quad.value = map[emp] || "S";
  const e = document.querySelector('[name="income_mix_e_pct"]');
  const s = document.querySelector('[name="income_mix_s_pct"]');
  const b = document.querySelector('[name="income_mix_b_pct"]');
  const i = document.querySelector('[name="income_mix_i_pct"]');
  if (!e || !s || !b || !i) return;
  if (emp === "side_hustle") {
    e.value = 60;
    s.value = 40;
    b.value = 0;
    i.value = 0;
  } else {
    e.value = emp === "employee" ? 100 : 0;
    s.value = quad.value === "S" ? 100 : 0;
    b.value = quad.value === "B" ? 100 : 0;
    i.value = quad.value === "I" ? 100 : 0;
  }
}

document.getElementById("employment-type")?.addEventListener("change", syncQuadrantFromEmployment);
document.getElementById("cashflow-quadrant")?.addEventListener("change", () => {
  if (document.getElementById("employment-type")?.value === "side_hustle") return;
  syncQuadrantFromEmployment();
});

EXPENSE_FIELDS.forEach(({ key }) => {
  document.querySelector(`[name="exp_${key}"]`)?.addEventListener("input", updateTotals);
});

async function collectAndSave(current) {
  if (current === 1) {
    const fd = formData(document.getElementById("form-1"));
    if (!fd.display_name?.trim()) throw new Error("Enter your name.");
    const mixTotal =
      Number(fd.income_mix_e_pct || 0) +
      Number(fd.income_mix_s_pct || 0) +
      Number(fd.income_mix_b_pct || 0) +
      Number(fd.income_mix_i_pct || 0);
    if (mixTotal > 0 && Math.abs(mixTotal - 100) > 2) {
      throw new Error("Income mix percentages should sum to about 100%.");
    }
    await saveStep(1, {
      display_name: fd.display_name.trim(),
      primary_trade: fd.primary_trade || "",
      employment_type: fd.employment_type,
      cashflow_quadrant_primary: fd.cashflow_quadrant_primary || "S",
      income_mix_e_pct: Number(fd.income_mix_e_pct || 0),
      income_mix_s_pct: Number(fd.income_mix_s_pct || 0),
      income_mix_b_pct: Number(fd.income_mix_b_pct || 0),
      income_mix_i_pct: Number(fd.income_mix_i_pct || 0),
    });
  } else if (current === 2) {
    if (!incomeStreams.length) throw new Error("Add at least one income source.");
    await saveStep(2, { income_streams: incomeStreams });
  } else if (current === 3) {
    const payload = {};
    EXPENSE_FIELDS.forEach(({ key }) => {
      payload[key] = Number(document.querySelector(`[name="exp_${key}"]`)?.value || 0);
    });
    await saveStep(3, payload);
  } else if (current === 4) {
    const fd = formData(document.getElementById("form-4-stability"));
    await saveStep(4, {
      bills,
      stability_fund_balance: Number(fd.stability_fund_balance || 0),
      stability_fund_target_months: Number(fd.stability_fund_target_months),
    });
  } else if (current === 5) {
    await saveStep(5, { debts });
  } else if (current === 6) {
    const fd = formData(document.getElementById("form-6"));
    await saveStep(6, {
      score_band: fd.score_band,
      estimated_score: fd.estimated_score ? Number(fd.estimated_score) : null,
      utilization_pct: Number(fd.utilization_pct || 0),
      total_credit_limit: Number(fd.total_credit_limit || 0),
      total_revolver_balance: Number(fd.total_revolver_balance || 0),
      late_payments_12mo: !!document.querySelector('[name="late_payments_12mo"]')?.checked,
      collections: !!document.querySelector('[name="collections"]')?.checked || collections.length > 0,
      collections_items: collections,
      charge_offs: Number(fd.charge_offs || 0),
      bankruptcies: Number(fd.bankruptcies || 0),
      inquiries_6mo: Number(fd.inquiries_6mo || 0),
    });
  } else if (current === 7) {
    const fd = formData(document.getElementById("form-7"));
    const total =
      Number(fd.profit_pct) + Number(fd.tax_pct) + Number(fd.owner_pay_pct) + Number(fd.opex_pct);
    if (Math.abs(total - 100) > 0.5) throw new Error("Business budget percentages must sum to 100.");
    await saveStep(7, {
      business_type: fd.business_type,
      monthly_revenue: Number(fd.monthly_revenue || 0),
      profit_pct: Number(fd.profit_pct),
      tax_pct: Number(fd.tax_pct),
      owner_pay_pct: Number(fd.owner_pay_pct),
      opex_pct: Number(fd.opex_pct),
    });
  } else if (current === 8) {
    await saveStep(8, { footprints });
  }
}

function loadSavedData(data) {
  if (!data) return;
  const f1 = document.getElementById("form-1");
  if (f1 && data.display_name) {
    f1.display_name.value = data.display_name;
    f1.primary_trade.value = data.primary_trade || "";
    f1.employment_type.value = data.employment_type || "self_employed";
    f1.cashflow_quadrant_primary.value = data.cashflow_quadrant_primary || "S";
    const mix = data.income_mix || {};
    f1.income_mix_e_pct.value = mix.E ?? mix.e_pct ?? 0;
    f1.income_mix_s_pct.value = mix.S ?? mix.s_pct ?? 100;
    f1.income_mix_b_pct.value = mix.B ?? mix.b_pct ?? 0;
    f1.income_mix_i_pct.value = mix.I ?? mix.i_pct ?? 0;
  }
  incomeStreams.splice(0, incomeStreams.length, ...(data.income_streams || []));
  bills.splice(0, bills.length, ...(data.bills || []));
  debts.splice(0, debts.length, ...(data.debts || []));
  collections.splice(0, collections.length, ...(data.collections_items || []));
  Object.assign(footprints, data.footprints || {});

  EXPENSE_FIELDS.forEach(({ key }) => {
    const input = document.querySelector(`[name="exp_${key}"]`);
    if (input && data.expenses) input.value = data.expenses[key] ?? 0;
  });

  const stab = document.getElementById("form-4-stability");
  if (stab) {
    stab.stability_fund_balance.value = data.stability_fund_balance ?? 0;
    stab.stability_fund_target_months.value = data.stability_fund_target_months ?? 4;
  }

  const credit = data.credit || {};
  const f6 = document.getElementById("form-6");
  if (f6) {
    f6.score_band.value = credit.score_band || "unknown";
    if (credit.estimated_score) f6.estimated_score.value = credit.estimated_score;
    f6.utilization_pct.value = credit.utilization_pct ?? 30;
    f6.total_credit_limit.value = credit.total_credit_limit ?? 0;
    f6.total_revolver_balance.value = credit.total_revolver_balance ?? 0;
    f6.charge_offs.value = credit.charge_offs ?? 0;
    f6.bankruptcies.value = credit.bankruptcies ?? 0;
    f6.inquiries_6mo.value = credit.inquiries_6mo ?? 0;
    document.querySelector('[name="late_payments_12mo"]').checked = !!credit.late_payments_12mo;
    document.querySelector('[name="collections"]').checked = !!credit.collections;
  }

  const biz = data.business_budget || {};
  const f7 = document.getElementById("form-7");
  if (f7) {
    f7.business_type.value = biz.business_type || "";
    f7.monthly_revenue.value = biz.monthly_revenue ?? data.monthly_gross_income ?? "";
    f7.profit_pct.value = biz.profit_pct ?? 5;
    f7.tax_pct.value = biz.tax_pct ?? 15;
    f7.owner_pay_pct.value = biz.owner_pay_pct ?? 50;
    f7.opex_pct.value = biz.opex_pct ?? 30;
  }

  renderIncomeStreams();
  renderBills();
  renderDebts();
  renderCollections();
  document.querySelectorAll(".connect-btn").forEach((btn) => {
    const source = btn.dataset.source;
    btn.classList.toggle("connected", !!footprints[source]);
  });
  updateTotals();
}

document.getElementById("btn-back").onclick = () => {
  if (step > 1) {
    step -= 1;
    showStep();
  }
};

document.getElementById("btn-next").onclick = async () => {
  document.getElementById("error").textContent = "";
  try {
    if (step < totalSteps) {
      await collectAndSave(step);
      step += 1;
      showStep();
      return;
    }
    if (EDIT_MODE) {
      await collectAndSave(step);
      window.location.href = "/static/index.html";
      return;
    }
    if (!document.getElementById("contract-check").checked) {
      document.getElementById("error").textContent = "Sign the contract to continue.";
      return;
    }
    const result = await fetchJson("/user/intake/complete", {
      method: "POST",
      body: JSON.stringify({ display_name: "Architect", focus_season_months: 6 }),
    });
    sessionStorage.setItem("welcome_message", result.identity_notification);
    window.location.href = "/static/index.html";
  } catch (e) {
    document.getElementById("error").textContent = e.message;
  }
};

(async () => {
  try {
    const status = await fetchJson("/user/intake/status");
    if (status.intake_completed && !EDIT_MODE) {
      window.location.href = "/static/index.html";
      return;
    }
    if (status.intake_step > 0 && !EDIT_MODE) {
      step = Math.min(status.intake_step + 1, totalSteps);
    }
    const data = await fetchJson("/user/intake/data");
    loadSavedData(data);
    if (EDIT_MODE) {
      document.querySelector("header h1").textContent = "Update your financial profile";
      document.getElementById("step-9")?.classList.add("hidden");
    }
  } catch {
    /* new user */
  }
  syncQuadrantFromEmployment();
  showStep();
})();
