/* Instrument behavior: inspection lamp, dial, number swap, one-question move stepper. */
(function () {
  const root = document.documentElement;
  const figure = document.getElementById("hero-figure");
  const sub = document.getElementById("hero-sub");
  const ticks = document.getElementById("tick-row");
  const modeWord = document.getElementById("mode-word");
  const modeLamp = document.getElementById("mode-lamp");
  const arc = document.getElementById("dial-arc");
  const fundArc = document.getElementById("dial-fund");
  if (!figure) return;

  window.addEventListener("pointermove", (event) => {
    root.style.setProperty("--mx", event.clientX + "px");
    root.style.setProperty("--my", event.clientY + "px");
  });

  const readings = [];
  let active = 0;
  const ctx = { summary: null, alloc: null, star: null, nw: null };
  const briefTitle = document.getElementById("brief-title");
  const briefWhat = document.getElementById("brief-what");
  const briefWhy = document.getElementById("brief-why");
  const briefSteps = document.getElementById("brief-steps");
  const briefAct = document.getElementById("brief-act");
  const modeWhy = document.getElementById("mode-why");

  function dollars(n) {
    return "$" + Math.round(Number(n) || 0).toLocaleString();
  }

  function explain(id) {
    const alloc = ctx.alloc || {};
    const summary = ctx.summary || {};
    const star = ctx.star || {};
    const pct = Number(alloc.stability_fund_pct ?? summary.stability_fund?.pct_of_target ?? 0);
    const mode = alloc.mode || "seed";
    const cap = dollars(alloc.risk_budget);
    const income = dollars(summary.monthly_gross_income);
    const essentials = dollars(summary.monthly_essentials);
    const surplus = dollars(alloc.surplus);
    if (id === "risk") {
      const why = mode === "seed"
        ? "The Stability Fund is " + pct + "% full. Under 50%, the cap is the smallest of 10% of leftover cash, 3% of income, and $250. The fund itself is never used for a bet."
        : mode === "measured"
          ? "The fund is " + pct + "% full. Past half full, the cap can rise, still never taken from the fund."
          : "The fund is " + pct + "% full. A larger bet is allowed, still capped, and still not taken from the fund.";
      return {
        title: "Max loss this month",
        what: cap + " is the most a single bet is allowed to lose. It is a ceiling, not a pile of money to spend.",
        why: why,
        steps: [
          "Learn: if the worst case is above " + cap + ", the move is a no.",
          "Plan: write the worst-case loss before the hoped-for profit.",
          "Do: you place the trade. This app only watches the deadline.",
        ],
        act: "Test an idea under " + cap,
        go: "moves",
      };
    }
    if (id === "income") {
      return {
        title: "Money in this month",
        what: income + " is what you told the system comes in. Every dollar gets a job before you spend it: 15% future, 65% essentials, 20% life.",
        why: "Bets are sized from what is left after essentials, not from the Stability Fund.",
        steps: [
          "Check the income line matches this month, not a hope.",
          "The next inflow gets split 15 / 65 / 20 before a want is bought.",
        ],
        act: "Edit the number if it is wrong",
        go: "edit",
      };
    }
    if (id === "essentials") {
      return {
        title: "Must-pay this month",
        what: essentials + " is housing, food, insurance, and debt minimums. This pile is untouchable.",
        why: "Leftover after this is " + surplus + ". That leftover is what a bet is allowed to come from.",
        steps: [
          "Do not fund a trade, flip, or Kalshi from this pile.",
          "If essentials are wrong, fix them before you trust the risk cap.",
        ],
        act: "Edit the number if it is wrong",
        go: "edit",
      };
    }
    if (id === "debt") {
      return {
        title: "What you owe",
        what: "This is the debt total on file. High-interest debt is paid from the future 15%, not by skipping essentials.",
        why: "No debts on file means the future slice can go to the Stability Fund first.",
        steps: [
          "If a debt is missing, add it so the snowball is real.",
          "A bet does not replace a debt payment.",
        ],
        act: "Edit debts",
        go: "edit",
      };
    }
    if (id === "fund") {
      return {
        title: "Stability Fund",
        what: pct + "% of the target is saved. The target is a few months of essentials, so a bad month does not force a bad bet.",
        why: mode === "seed"
          ? "Under 50% is why bets stay in small-test mode."
          : "Past 50%, the risk cap is allowed to grow.",
        steps: [
          "Next inflow: 15% goes here until the fund is full.",
          "Do not withdraw this to cover a trade.",
        ],
        act: "See this month's split",
        go: "pulse",
      };
    }
    if (id === "net") {
      const need = dollars(star.required_monthly_gain);
      return {
        title: "Net worth",
        what: "Assets minus debts. The North Star pace is " + (star.pct_of_target ?? 0) + "% of the target.",
        why: "To stay on pace you need about " + need + " of net-worth gain a month. That is not the same as the bet cap.",
        steps: [
          "Fill cash, tools, and investments if those boxes are empty.",
          "A bet only helps if the worst case fits under " + cap + ".",
        ],
        act: "Fill the missing asset boxes",
        go: "pulse",
      };
    }
    return {
      title: "This number",
      what: "Pick a label under the figure.",
      why: "",
      steps: [],
      act: "See the month",
      go: "pulse",
    };
  }

  function showBrief(id) {
    const card = explain(id);
    if (briefTitle) briefTitle.textContent = card.title;
    if (briefWhat) briefWhat.textContent = card.what;
    if (briefWhy) briefWhy.textContent = card.why;
    if (briefSteps) {
      briefSteps.innerHTML = "";
      card.steps.forEach((line) => {
        const item = document.createElement("li");
        item.textContent = line;
        briefSteps.appendChild(item);
      });
    }
    if (briefAct) {
      briefAct.textContent = card.act;
      briefAct.dataset.go = card.go === "edit" ? "" : card.go;
      briefAct.onclick = () => {
        if (card.go === "edit") {
          window.location.href = "/static/onboarding.html?edit=1";
          return;
        }
        const button = document.querySelector('.deck-btn[data-deck="' + card.go + '"]');
        if (button) button.click();
        const target = card.go === "moves" ? document.getElementById("smart-moves-card") : document.getElementById("missions-card");
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      };
    }
  }

  function setArc(el, radius, pct) {
    if (!el) return;
    const length = 2 * Math.PI * radius;
    const clamped = Math.max(0, Math.min(100, Number(pct) || 0));
    el.style.strokeDasharray = String(length);
    el.style.strokeDashoffset = String(length * (1 - clamped / 100));
  }

  function paintFigure(index) {
    const item = readings[index];
    if (!item) return;
    active = index;
    sub.textContent = item.label;
    figure.classList.remove("pop");
    void figure.offsetWidth;
    figure.classList.add("pop");
    const target = Number(item.value) || 0;
    const prefix = item.money ? "$" : "";
    const suffix = item.suffix || "";
    const started = performance.now();
    function frame(now) {
      const progress = Math.min(1, (now - started) / 650);
      const eased = 1 - Math.pow(1 - progress, 3);
      const shown = Math.round(target * eased);
      figure.textContent = prefix + shown.toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    ticks.querySelectorAll(".tick").forEach((button, i) => {
      button.classList.toggle("on", i === index);
    });
    showBrief(item.id);
    renderLens(item.id);
  }

  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text != null) el.textContent = text;
    return el;
  }

  function play(title, detail) {
    const item = node("li");
    item.appendChild(node("b", "", title));
    item.appendChild(node("span", "", detail));
    return item;
  }

  function renderLens(id) {
    const lens = document.getElementById("lens");
    if (!lens) return;
    const onPulse = (document.body.dataset.view || "pulse") === "pulse";
    if (!onPulse) {
      lens.hidden = true;
      return;
    }
    document.body.dataset.lens = id;
    lens.hidden = false;
    lens.replaceChildren();
    const summary = ctx.summary || {};
    const alloc = ctx.alloc || {};
    const star = ctx.star || {};
    const fund = summary.stability_fund || {};
    const income = Number(summary.monthly_gross_income) || 0;
    const essentials = Number(summary.monthly_essentials) || 0;
    const future = Math.round(income * 0.15);
    const cap = Math.round(Number(alloc.risk_budget) || 0);
    const fundTarget = Number(fund.target) || essentials * 4;
    const half = fundTarget / 2;
    const balance = Number(fund.balance) || 0;
    const monthsToHalf = future > 0 ? Math.ceil(Math.max(0, half - balance) / future) : 0;
    const streams = (summary.income_breakdown && summary.income_breakdown.streams) || [];
    const trade = (streams[0] && streams[0].name) || "your main skill";
    const pace = dollars(star.required_monthly_gain);
    const monthsLeft = star.months_left || "";
    const targetDate = star.target_date || "the target date";

    const kicker = node("p", "lens-kicker");
    const title = node("h2");
    const lead = node("p", "lens-lead");
    const list = node("ol", "plays");
    const actions = node("div", "lens-actions");

    function goButton(label, deck) {
      const button = node("button", "btn", label);
      button.type = "button";
      button.addEventListener("click", () => {
        const tab = document.querySelector('.deck-btn[data-deck="' + deck + '"]');
        if (tab) tab.click();
        const target = deck === "moves" ? document.getElementById("smart-moves-card") : null;
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      return button;
    }

    if (id === "risk") {
      kicker.textContent = "This page is the bet plan";
      title.textContent = "Win small until the fund is half full";
      lead.textContent = dollars(cap) + " is the most one bet may lose. A win this month is a test that cannot lose more than that, or a job you sell with no money down. Chasing a big trade now is how this month loses.";
      list.append(
        play("Do this first — no money at risk", "Turn " + trade + " into one fixed-price offer this week. That is income you can repeat. It does not touch the $" + cap + " cap."),
        play("Only bet if the exit is written", "A flip, trade, crypto, or Kalshi is allowed only if the worst case is " + dollars(cap) + " or less and the money is back inside 14 days. You place it. This app does not."),
        play("Not yet", "Anything that can lose more than " + dollars(cap) + " is a no. Do not use the Stability Fund, rent, or gas money to cover it."),
        play("How the cap gets bigger", "Half a full fund is about " + dollars(half) + ". Put " + dollars(future) + " of the next inflow into the fund. About " + monthsToHalf + " months of that reaches half full, and only then can the bet cap rise.")
      );
      actions.appendChild(goButton("Write the bet under " + dollars(cap), "moves"));
    } else if (id === "net") {
      kicker.textContent = "This page is the path to the target";
      title.textContent = "Do not chase " + pace + " a month";
      lead.textContent = pace + " is only the raw split of the remaining target across about " + monthsLeft + " months until " + targetDate + ", starting from what is on file now. It is a warning that the date is too close for a $0 net worth. It is not this month's job.";
      list.append(
        play("This month's job", "Park " + dollars(future) + " in the Stability Fund. Enter cash, tools, and the van if you own them, or the $0 net worth is incomplete, not true."),
        play("This week's job", "Price one " + trade + " offer. A repeatable job moves net worth. A " + dollars(cap) + " bet does not get you to the target."),
        play("Later", "After the fund is about " + dollars(half) + " (half full), the bet cap is allowed to grow. Assets come after the fund, not before it.")
      );
      actions.appendChild(goButton("Price one offer as a move", "moves"));
    } else if (id === "fund") {
      kicker.textContent = "This page is the fund plan";
      title.textContent = "The fund is why bets stay tiny";
      lead.textContent = "You are at " + (fund.pct_of_target || 0) + "% of a " + dollars(fundTarget) + " fund (" + (fund.target_months || 4) + " months of essentials). Under 50%, every bet stays at " + dollars(cap) + " max loss.";
      list.append(
        play("Next dollar in", dollars(future) + " (15% of income) goes here before a want and before a bet."),
        play("Halfway", dollars(half) + " saved is the door to a larger risk budget. At " + dollars(future) + " a month, that is about " + monthsToHalf + " months."),
        play("Rule", "Never pull this fund out to pay for a trade.")
      );
    } else if (id === "income") {
      kicker.textContent = "This page is the split";
      title.textContent = "Give the " + dollars(income) + " a job before you spend it";
      lead.textContent = "15% future is " + dollars(future) + ". 65% essentials cap is " + dollars(income * 0.65) + ". 20% life is " + dollars(income * 0.2) + ". Your real must-pay bills are " + dollars(essentials) + ", which fits under the cap.";
      list.append(
        play("Future " + dollars(future), "This is the Stability Fund payment. It is also what later raises the bet cap."),
        play("Do not skim it for a bet", "A bet comes only from the " + dollars(cap) + " max-loss ceiling, not from this inflow.")
      );
    } else if (id === "essentials") {
      kicker.textContent = "This page is the locked pile";
      title.textContent = dollars(essentials) + " does not fund a bet";
      lead.textContent = "Housing, food, insurance, gas, and the business costs on the personal account stay paid. Gas is a large line. If the job needs it, it is operating cost.";
      list.append(
        play("Locked", "Do not move rent, gas, or insurance into a flip, trade, or Kalshi."),
        play("Check", "If a line is wrong, fix it. A wrong essentials number makes the " + dollars(cap) + " cap a lie.")
      );
      const edit = node("a", "btn btn-secondary", "Fix a number");
      edit.href = "/static/onboarding.html?edit=1";
      actions.appendChild(edit);
    } else if (id === "debt") {
      kicker.textContent = "This page is the debt plan";
      title.textContent = "Nothing is on file to pay down";
      lead.textContent = "With no debt listed, the " + dollars(future) + " future slice goes to the Stability Fund, not a snowball. If a balance exists and is missing here, the plan is wrong.";
      list.append(
        play("Add it or ignore the snowball", "A hidden card or loan still has to be paid. Add it before you trust this page."),
        play("Do not borrow to bet", "Loan readiness is not permission to fund a trade with credit.")
      );
      const edit = node("a", "btn btn-secondary", "Add a debt if one exists");
      edit.href = "/static/onboarding.html?edit=1";
      actions.appendChild(edit);
    } else {
      kicker.textContent = "Plan";
      title.textContent = "Pick a number";
      lead.textContent = "Each label replaces this page with the plan for that number.";
    }

    const full = node("button", "btn btn-secondary", "Show every number");
    full.type = "button";
    full.addEventListener("click", () => {
      delete document.body.dataset.lens;
      lens.hidden = true;
    });
    actions.appendChild(full);
    lens.append(kicker, title, lead, list, actions);
  }

  function upsert(label, value, extra) {
    const found = readings.find((item) => item.label === label);
    const next = Object.assign({ label, value, money: true }, extra);
    if (found) Object.assign(found, next);
    else readings.push(next);
    ticks.innerHTML = "";
    readings.forEach((item, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tick" + (index === active ? " on" : "");
      button.textContent = item.label;
      button.addEventListener("click", () => paintFigure(index));
      ticks.appendChild(button);
    });
    if (readings.length === 1) paintFigure(0);
  }

  document.addEventListener("reality:ready", (event) => {
    const summary = event.detail || {};
    ctx.summary = summary;
    upsert("Income", summary.monthly_gross_income, { money: true, id: "income" });
    upsert("Essentials", summary.monthly_essentials, { money: true, id: "essentials" });
    upsert("Debt", summary.debt_total, { money: true, id: "debt" });
    const fund = summary.stability_fund ? summary.stability_fund.pct_of_target : 0;
    upsert("Fund", fund, { money: false, suffix: "%", id: "fund" });
    setArc(fundArc, 68, fund);
  });

  document.addEventListener("omni:ready", (event) => {
    const detail = event.detail || {};
    const net = detail.nw && detail.nw.net_worth;
    const star = detail.star || {};
    const alloc = detail.alloc || {};
    ctx.star = star;
    ctx.nw = detail.nw || null;
    ctx.alloc = alloc;
    upsert("Net worth", net, { money: true, id: "net" });
    upsert("Max loss", alloc.risk_budget, { money: true, id: "risk" });
    setArc(arc, 86, star.pct_of_target);
    const mode = String(alloc.mode || "seed");
    const names = { seed: "Small tests only", measured: "Measured bets", deploy: "Larger bets allowed" };
    modeWord.textContent = names[mode] || mode;
    const pct = alloc.stability_fund_pct ?? 0;
    if (modeWhy) {
      modeWhy.textContent = mode === "seed"
        ? "Stability Fund is " + pct + "% full, so this stays on small tests. Clicking a number does not change this."
        : "Stability Fund is " + pct + "% full. Clicking a number explains that number. It does not change this bet size.";
    }
    modeLamp.classList.toggle("pulse", mode === "seed");
    modeLamp.classList.toggle("steady", mode !== "seed");
    const riskIndex = readings.findIndex((item) => item.id === "risk");
    if (riskIndex >= 0) paintFigure(riskIndex);
  });

  function go(name) {
    const button = document.querySelector('.deck-btn[data-deck="' + name + '"]');
    if (!button) return;
    document.body.classList.add("switching");
    button.click();
    window.setTimeout(() => document.body.classList.remove("switching"), 520);
    const first = document.querySelector('[data-deck="' + name + '"]:not(.deck-btn)');
    if (first) first.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  document.querySelectorAll("[data-go]").forEach((node) => {
    node.addEventListener("click", () => go(node.getAttribute("data-go")));
  });

  document.querySelectorAll(".deck-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.body.classList.add("switching");
      window.setTimeout(() => {
        document.body.classList.remove("switching");
        const lens = document.getElementById("lens");
        if (!lens) return;
        const onPulse = (document.body.dataset.view || "pulse") === "pulse";
        if (!onPulse) lens.hidden = true;
        else if (document.body.dataset.lens) {
          lens.hidden = false;
          renderLens(document.body.dataset.lens);
        }
      }, 0);
    });
  });

  document.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("pointermove", (event) => {
      const box = card.getBoundingClientRect();
      card.style.setProperty("--lx", (event.clientX - box.left) + "px");
      card.style.setProperty("--ly", (event.clientY - box.top) + "px");
    });
  });

  window.addEventListener("pointermove", (event) => {
    root.style.setProperty("--hx", (event.clientX / window.innerWidth * 100) + "%");
  });

  document.addEventListener("keydown", (event) => {
    if (event.target && /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
    const keys = { "1": "pulse", "2": "moves", "3": "desk" };
    const name = keys[event.key];
    if (!name) return;
    const button = document.querySelector('.deck-btn[data-deck="' + name + '"]');
    if (button) button.click();
  });

  const form = document.getElementById("smart-move-form");
  if (!form) return;
  const fields = Array.from(form.querySelectorAll("label"));
  const submit = form.querySelector('button[type="submit"]');
  let step = 0;
  const expects = [
    "Name the idea",
    "What kind of move",
    "Where you will do it",
    "Money you put in",
    "Money you hope to make",
    "Most you can lose",
    "Days until it comes back",
    "How you get out",
  ];
  const expect = document.createElement("p");
  expect.className = "step-expect";
  const lamps = document.createElement("div");
  lamps.className = "step-lamps";
  fields.forEach(() => {
    const lamp = document.createElement("i");
    lamps.appendChild(lamp);
  });
  const nav = document.createElement("div");
  nav.className = "step-nav";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "btn btn-secondary";
  back.textContent = "Back";
  const next = document.createElement("button");
  next.type = "button";
  next.className = "btn";
  next.textContent = "Next";
  nav.appendChild(back);
  nav.appendChild(next);
  form.insertBefore(lamps, form.firstChild);
  form.insertBefore(expect, form.firstChild);
  form.appendChild(nav);

  function showStep() {
    fields.forEach((field, index) => field.classList.toggle("step-off", index !== step));
    Array.from(lamps.children).forEach((lamp, index) => lamp.classList.toggle("on", index === step));
    back.style.visibility = step === 0 ? "hidden" : "visible";
    const last = step === fields.length - 1;
    next.classList.toggle("step-off", last);
    if (submit) submit.classList.toggle("step-off", !last);
    expect.textContent = expects[step] || "";
  }
  next.addEventListener("click", () => {
    const current = fields[step].querySelector("input, select, textarea");
    if (current && !current.checkValidity()) {
      current.reportValidity();
      return;
    }
    step = Math.min(fields.length - 1, step + 1);
    showStep();
  });
  back.addEventListener("click", () => {
    step = Math.max(0, step - 1);
    showStep();
  });
  showStep();
})();
