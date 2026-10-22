"""OmniWealth — one engine for net worth, capital pools, and smart-risk moves.

Simple picture:
- **Protect first**: Stability Fund is never used for bets.
- **Then take measured shots**: a capped "risk budget" for flips, trades, crypto, Kalshi, etc.
- **Two keys**: every move gets a bull case AND a kill case before you can commit.
- **Execute = checklist, not autopilot**: this code never sends money. It tells you
  exactly what to do, then tracks the move after you confirm you did it.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

MOVE_TYPES = (
    "flip",
    "trade",
    "crypto",
    "kalshi",
    "business_reinvest",
    "equipment",
    "acquisition",
    "other",
)

SPECULATIVE_TYPES = {"trade", "crypto", "kalshi"}
FAST_CYCLE_TYPES = {"flip", "trade", "crypto", "kalshi"}

VERDICTS = ("BUY", "TEST", "WAIT", "RENEGOTIATE", "REJECT", "ESCALATE")

POOL_ORDER = (
    "survival",
    "operating",
    "tax",
    "reserve",
    "opportunity",
    "growth",
    "investment",
    "speculative",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(raw: str | list | dict | None, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw or "")
    except json.JSONDecodeError:
        return default


def _money(n: float) -> float:
    return round(float(n or 0), 2)


def build_net_worth(profile) -> dict[str, Any]:
    """Combine intake numbers + optional wealth_state_json into a net-worth picture."""
    stored = _loads(getattr(profile, "wealth_state_json", None), {})
    debts = _loads(profile.debts_json, [])
    debt_total = _money(sum(float(d.get("balance") or 0) for d in debts if isinstance(d, dict)))
    credit = _loads(profile.credit_snapshot_json, {})
    collections = credit.get("collections_items") or []
    collections_total = _money(
        sum(float(c.get("balance") or 0) for c in collections if isinstance(c, dict))
    )

    cash = _money(stored.get("cash", profile.stability_fund_balance or 0))
    business_cash = _money(stored.get("business_accounts", 0))
    productive = _money(stored.get("productive_assets", 0))
    investments = _money(stored.get("investments", 0))
    receivables = _money(stored.get("receivables", 0))
    business_equity = _money(stored.get("business_equity", 0))
    other_assets = _money(stored.get("other_assets", 0))
    loans = _money(stored.get("loans", debt_total))
    tax_owed = _money(stored.get("tax_liabilities", 0))
    other_liabilities = _money(stored.get("other_liabilities", collections_total))

    assets = cash + business_cash + productive + investments + receivables + business_equity + other_assets
    liabilities = loans + tax_owed + other_liabilities
    net = _money(assets - liabilities)

    missing = []
    if productive <= 0 and not stored.get("productive_assets_known"):
        missing.append("productive_assets")
    if business_equity <= 0 and not stored.get("business_equity_known"):
        missing.append("business_equity")

    status = "INCOMPLETE" if missing else "COMPLETE"
    return {
        "status": status,
        "missing": missing,
        "assets": {
            "cash": cash,
            "business_accounts": business_cash,
            "productive_assets": productive,
            "investments": investments,
            "receivables": receivables,
            "business_equity": business_equity,
            "other_assets": other_assets,
            "total": _money(assets),
        },
        "liabilities": {
            "loans_and_cards": loans,
            "tax_liabilities": tax_owed,
            "other_liabilities": other_liabilities,
            "total": _money(liabilities),
        },
        "net_worth": net,
        "as_of": stored.get("as_of") or _now_iso()[:10],
        "note": (
            "Incomplete is OK — we still guide you. Fill missing asset values when you can."
            if missing
            else "Baseline is complete enough to underwrite moves."
        ),
    }


def compute_trajectory(profile, net_worth: dict[str, Any] | None = None) -> dict[str, Any]:
    """How far you are from the North Star target (default: $1M)."""
    star = _loads(getattr(profile, "north_star_json", None), {})
    target = _money(star.get("target_net_worth", 1_000_000))
    target_date = star.get("target_date") or "2027-12-31"
    label = star.get("label") or "North Star — financial freedom target"
    nw = (net_worth or build_net_worth(profile))["net_worth"]
    remaining = max(0.0, _money(target - nw))
    pct = round((nw / target * 100) if target else 0, 1)

    months_left = 12.0
    try:
        end = datetime.fromisoformat(str(target_date)).date()
        today = datetime.now(timezone.utc).date()
        months_left = max(1.0, (end.year - today.year) * 12 + (end.month - today.month))
    except ValueError:
        months_left = 12.0

    required_monthly = _money(remaining / months_left) if remaining else 0.0
    return {
        "label": label,
        "target_net_worth": target,
        "target_date": target_date,
        "current_net_worth": nw,
        "pct_of_target": pct,
        "remaining": remaining,
        "months_left": round(months_left, 1),
        "required_monthly_gain": required_monthly,
        "on_pace": nw >= target or required_monthly <= _money((profile.monthly_gross_income or 0) * 0.15),
    }


def allocate_capital(profile) -> dict[str, Any]:
    """Waterfall: protect survival, then tax, then a capped speculative pool for bets."""
    income = _money(profile.monthly_gross_income)
    essentials = _money(profile.monthly_essentials)
    surplus = _money(max(0.0, income - essentials))
    future = _money(income * 0.15)
    life = _money(income * 0.20)
    fund = _money(profile.stability_fund_balance)
    target_months = int(profile.stability_fund_target_months or 4)
    fund_target = _money(essentials * target_months)
    fund_gap = _money(max(0.0, fund_target - fund))

    tax_need = _money(income * 0.15)
    # Opportunity / speculative: never raid the Stability Fund.
    # If the fund is thin, keep bets small (TEST size). If funded, allow a real risk budget.
    fund_pct = (fund / fund_target * 100) if fund_target else 0
    if fund_pct < 50:
        speculative_cap = _money(min(surplus * 0.10, income * 0.03, 250))
        mode = "seed"  # tiny tests only
    elif fund_pct < 100:
        speculative_cap = _money(min(surplus * 0.20, future * 0.40, 750))
        mode = "measured"
    else:
        speculative_cap = _money(min(surplus * 0.35, future * 0.60, 2500))
        mode = "deploy"

    opportunity_pool = _money(max(0.0, future - min(future, fund_gap / 4 if fund_gap else 0)))
    speculative_pool = _money(min(speculative_cap, max(0.0, surplus * 0.25 if surplus else speculative_cap)))

    pools = {
        "survival": {"amount": min(essentials, income), "job": "Housing, food, insurance, debt minimums — untouchable."},
        "operating": {"amount": _money(essentials * 0.1), "job": "Keep the business running this month."},
        "tax": {"amount": tax_need, "job": "Set aside for quarterly estimates — not optional."},
        "reserve": {"amount": _money(min(future, fund_gap / max(target_months, 1))), "job": "Fill Stability Fund first."},
        "opportunity": {"amount": opportunity_pool, "job": "Flips, equipment, skill assets with a recycle plan."},
        "growth": {"amount": _money(surplus * 0.15 if fund_pct >= 50 else 0), "job": "Reinvest in the business when it beats external bets."},
        "investment": {"amount": _money(surplus * 0.10 if fund_pct >= 100 else 0), "job": "Longer-hold assets after the fund is full."},
        "speculative": {"amount": speculative_pool, "job": "Crypto, Kalshi, short trades — capped, never from the fund."},
    }
    for name, pool in pools.items():
        pool["amount"] = _money(pool["amount"])

    return {
        "mode": mode,
        "monthly_income": income,
        "monthly_essentials": essentials,
        "surplus": surplus,
        "stability_fund_pct": round(fund_pct, 1),
        "risk_budget": speculative_pool,
        "max_single_loss": _money(speculative_pool),
        "rule": "Stability Fund is never the source of a bet. Risk budget is the ceiling for max plausible loss.",
        "pools": pools,
        "order": list(POOL_ORDER),
    }


def assess_financing_factors(profile) -> dict[str, Any]:
    """Seven credit factors — no fake 'you will be approved' prediction."""
    credit = _loads(profile.credit_snapshot_json, {})
    util = float(credit.get("utilization_pct") or 0)
    score = credit.get("estimated_score")
    band = credit.get("score_band") or "unknown"
    late = bool(credit.get("late_payments_12mo"))
    collections = bool(credit.get("collections")) or bool(credit.get("collections_items"))
    inquiries = int(credit.get("inquiries_6mo") or 0)
    charge_offs = int(credit.get("charge_offs") or 0)

    factors = [
        {
            "id": "payment_history",
            "label": "Payment history",
            "status": "watch" if late else "ok",
            "detail": "Late payments in last 12 months" if late else "No recent late payments reported",
        },
        {
            "id": "utilization",
            "label": "Credit utilization",
            "status": "watch" if util > 30 else "ok",
            "detail": f"{util:.0f}% of limits used — aim under 30%",
        },
        {
            "id": "score_band",
            "label": "Score band",
            "status": "watch" if band in ("poor", "fair", "unknown") else "ok",
            "detail": f"{band}" + (f" (~{score})" if score else ""),
        },
        {
            "id": "collections",
            "label": "Collections / charge-offs",
            "status": "watch" if collections or charge_offs else "ok",
            "detail": f"Collections={collections}, charge-offs={charge_offs}",
        },
        {
            "id": "inquiries",
            "label": "Recent inquiries",
            "status": "watch" if inquiries > 3 else "ok",
            "detail": f"{inquiries} hard pulls in 6 months",
        },
        {
            "id": "mix",
            "label": "Account mix",
            "status": "ok",
            "detail": "Self-reported — keep a mix of revolving and installment if you use credit.",
        },
        {
            "id": "stability_cushion",
            "label": "Cash cushion for lenders",
            "status": "watch" if (profile.stability_fund_balance or 0) < (profile.monthly_essentials or 0) * 2 else "ok",
            "detail": "Lenders care that you can absorb a bad month.",
        },
    ]
    return {
        "factors": factors,
        "watch_count": sum(1 for f in factors if f["status"] == "watch"),
        "disclaimer": "Educational snapshot — not a credit score prediction or loan offer.",
    }


def compare_reinvestment(
    capital: float,
    internal_return_pct: float,
    external_return_pct: float,
    days: int = 30,
    track_record: str = "thin",
) -> dict[str, Any]:
    """Should the next dollar go into your business or an outside bet?"""
    capital = _money(capital)
    internal = capital * (internal_return_pct / 100)
    external = capital * (external_return_pct / 100)
    winner = "internal" if internal >= external else "external"
    if track_record in ("none", "thin") and internal_return_pct > external_return_pct * 1.5:
        winner = "test_internal"
        note = "Business looks better on paper, but evidence is thin — run a small TEST, not a full BUY."
    else:
        note = "Put the dollar where expected return is higher after friction."
    return {
        "capital": capital,
        "period_days": days,
        "internal_expected_profit": _money(internal),
        "external_expected_profit": _money(external),
        "winner": winner,
        "note": note,
    }


def _bull_case(move: dict[str, Any]) -> dict[str, Any]:
    capital = _money(move.get("capital_required") or move.get("capital") or 0)
    best = _money(move.get("best_profit") or move.get("expected_profit") or 0)
    likely = _money(move.get("likely_profit") or best * 0.6)
    recycle = int(move.get("recycle_days") or 30)
    velocity = round((likely / capital) * (30 / max(recycle, 1)), 3) if capital else 0
    return {
        "perspective": "Opportunity Scanner — bull case",
        "best_profit": best,
        "likely_profit": likely,
        "recycle_days": recycle,
        "monthly_velocity": velocity,
        "why": move.get("bull_why")
        or "If the thesis holds, capital comes back faster than a slow investment.",
    }


def _kill_case(move: dict[str, Any], risk_budget: float) -> dict[str, Any]:
    capital = _money(move.get("capital_required") or move.get("capital") or 0)
    max_loss = _money(move.get("max_loss") or capital)
    recycle = int(move.get("recycle_days") or 30)
    move_type = (move.get("move_type") or "other").lower()
    reasons = []
    if max_loss > risk_budget:
        reasons.append(f"Max loss ${max_loss:,.0f} exceeds risk budget ${risk_budget:,.0f}.")
    if move_type in SPECULATIVE_TYPES and recycle > 14:
        reasons.append("Speculative capital is stuck longer than 14 days — velocity is weak.")
    if not move.get("exit_plan"):
        reasons.append("No written exit (when to sell, stop-loss, or walk away).")
    if move.get("seller_claim") and not move.get("independent_evidence"):
        reasons.append("Numbers come from the seller — treat as unverified until proven.")
    if capital <= 0:
        reasons.append("Capital required is missing — cannot underwrite a $0 unknown.")
    kill_score = min(100, 20 * len(reasons) + (25 if max_loss >= capital else 0))
    return {
        "perspective": "Risk Officer — kill case",
        "max_loss": max_loss,
        "kill_score": kill_score,
        "reasons": reasons or ["No automatic kill flags — still size the bet to the risk budget."],
        "recommendation": "REJECT" if kill_score >= 60 else ("WAIT" if reasons else "CHALLENGE"),
    }


def _verdict(bull: dict, kill: dict, move: dict, allocation: dict) -> str:
    move_type = (move.get("move_type") or "other").lower()
    max_loss = kill["max_loss"]
    mode = allocation["mode"]
    if max_loss > allocation["risk_budget"] + 0.01:
        return "REJECT"
    if kill["kill_score"] >= 80:
        return "REJECT"
    if mode == "seed" and move_type in SPECULATIVE_TYPES:
        return "TEST" if max_loss <= allocation["risk_budget"] else "WAIT"
    if not move.get("exit_plan"):
        return "WAIT"
    if kill["kill_score"] >= 40:
        return "TEST"
    if bull["monthly_velocity"] <= 0:
        return "WAIT"
    if move_type in SPECULATIVE_TYPES:
        return "TEST"
    if mode == "deploy" and bull["likely_profit"] > 0 and max_loss <= allocation["risk_budget"]:
        return "BUY"
    return "TEST"


def execution_playbook(move: dict[str, Any], verdict: str, risk_budget: float) -> list[dict[str, str]]:
    """Human steps — the system never places the trade for you."""
    name = move.get("name") or "this move"
    platform = move.get("platform") or "your platform"
    capital = _money(move.get("capital_required") or move.get("capital") or 0)
    size = _money(min(capital, risk_budget)) if risk_budget else capital
    move_type = (move.get("move_type") or "other").lower()
    steps = [
        {"id": "size", "action": f"Size the position at ${size:,.0f} or less (risk budget ${risk_budget:,.0f})."},
        {"id": "exit", "action": move.get("exit_plan") or "Write the exit: profit target, stop-loss, and calendar date."},
        {"id": "source", "action": f"Use only surplus / speculative pool — not rent, tax, or Stability Fund money."},
    ]
    if move_type == "kalshi":
        steps.append({"id": "platform", "action": f"On Kalshi, confirm contract rules and settlement date for {name}."})
    elif move_type == "crypto":
        steps.append({"id": "platform", "action": f"On {platform}, set a hard stop. No leverage unless underwriting said so."})
    elif move_type == "flip":
        steps.append({"id": "platform", "action": f"Buy only after comparable sold prices (not asking prices) support the spread."})
    elif move_type == "trade":
        steps.append({"id": "platform", "action": f"Place the order on {platform} with the written stop already in the ticket."})
    else:
        steps.append({"id": "platform", "action": f"Execute on {platform} exactly as underwritten — no 'while I'm here' extras."})
    if verdict in ("TEST", "WAIT"):
        steps.append({"id": "cap", "action": "This is a TEST. Use a smaller size if you feel urgency — urgency is a kill flag."})
    steps.append({"id": "log", "action": "Come back here and tap Commit after you actually did the step — so we can monitor it."})
    return steps


def evaluate_move(profile, move: dict[str, Any]) -> dict[str, Any]:
    """Two-key underwrite: bull + kill + verdict + playbook."""
    move_type = (move.get("move_type") or "other").lower()
    if move_type not in MOVE_TYPES:
        move_type = "other"
        move = {**move, "move_type": move_type}

    allocation = allocate_capital(profile)
    bull = _bull_case(move)
    kill = _kill_case(move, allocation["risk_budget"])
    verdict = _verdict(bull, kill, move, allocation)
    if move.get("override") and move.get("override_reason") and verdict == "REJECT":
        if kill["max_loss"] <= allocation["risk_budget"] * 1.25:
            verdict = "ESCALATE"
        # still never let max_loss raid more than 1.25x budget even with override

    can_commit = verdict in ("BUY", "TEST", "ESCALATE")
    return {
        "move_id": move.get("move_id") or str(uuid.uuid4()),
        "name": move.get("name") or "Untitled move",
        "move_type": move_type,
        "platform": move.get("platform") or "",
        "capital_required": _money(move.get("capital_required") or move.get("capital") or 0),
        "verdict": verdict,
        "can_commit": can_commit,
        "assurance": {
            "risk_budget": allocation["risk_budget"],
            "max_loss": kill["max_loss"],
            "within_budget": kill["max_loss"] <= allocation["risk_budget"] + 0.01,
            "stability_fund_untouched": True,
            "two_key_complete": True,
        },
        "bull_case": bull,
        "kill_case": kill,
        "playbook": execution_playbook(move, verdict, allocation["risk_budget"]),
        "monitor": {
            "recycle_days": int(move.get("recycle_days") or 30),
            "review_by": (datetime.now(timezone.utc) + timedelta(days=int(move.get("recycle_days") or 7))).date().isoformat(),
            "fail_if": "Capital not recycled by review date, or loss exceeds max_loss.",
        },
        "disclaimer": (
            "This is a decision system, not a broker. It will not place trades, buy crypto, "
            "or move bank funds. You execute the playbook. Past patterns do not guarantee profit."
        ),
        "evaluated_at": _now_iso(),
    }


def list_moves(profile) -> list[dict[str, Any]]:
    return _loads(getattr(profile, "opportunities_json", None), [])


def upsert_move(profile, packet: dict[str, Any], *, status: str = "underwritten") -> list[dict[str, Any]]:
    moves = list_moves(profile)
    row = {
        "move_id": packet["move_id"],
        "name": packet["name"],
        "move_type": packet["move_type"],
        "verdict": packet["verdict"],
        "status": status,
        "capital_required": packet["capital_required"],
        "max_loss": packet["assurance"]["max_loss"],
        "review_by": packet["monitor"]["review_by"],
        "playbook": packet.get("playbook") or [],
        "updated_at": _now_iso(),
        "committed_at": packet.get("committed_at"),
        "result": packet.get("result"),
    }
    found = False
    for i, existing in enumerate(moves):
        if existing.get("move_id") == row["move_id"]:
            moves[i] = {**existing, **row}
            found = True
            break
    if not found:
        moves.insert(0, row)
    profile.opportunities_json = json.dumps(moves[:80])
    return moves


def weekly_review(profile) -> dict[str, Any]:
    nw = build_net_worth(profile)
    traj = compute_trajectory(profile, nw)
    alloc = allocate_capital(profile)
    credit = assess_financing_factors(profile)
    moves = list_moves(profile)
    open_moves = [m for m in moves if m.get("status") in ("committed", "open", "underwritten")]
    today = datetime.now(timezone.utc).date().isoformat()
    stale = [m for m in open_moves if (m.get("review_by") or "") <= today]
    return {
        "net_worth": nw,
        "trajectory": traj,
        "allocation": alloc,
        "financing": credit,
        "open_moves": open_moves,
        "stale_moves": stale,
        "this_week": [
            "Protect Stability Fund — no bets from it.",
            f"Risk budget this month: ${alloc['risk_budget']:,.0f} max loss.",
            "Underwrite every new idea (flip, trade, crypto, Kalshi) before money moves.",
            "Close or extend any move past its review date.",
        ],
    }


def command_center_payload(profile) -> dict[str, Any]:
    nw = build_net_worth(profile)
    return {
        "net_worth": nw,
        "trajectory": compute_trajectory(profile, nw),
        "allocation": allocate_capital(profile),
        "financing": assess_financing_factors(profile),
        "moves": list_moves(profile),
        "move_types": list(MOVE_TYPES),
    }


# ---------------------------------------------------------------------------
# Daily money router — every deposit gets a plan the same day.
# ---------------------------------------------------------------------------

RESEARCHED_ON = "2026-10-21"
DEBT_APR_THRESHOLD = 7.5
SELF_EMPLOYED_TAX_FLOOR = 25.0

TAX_DUE_DATES = (
    ("2026-04-15", "Q1 2026"),
    ("2026-06-15", "Q2 2026"),
    ("2026-09-15", "Q3 2026"),
    ("2027-01-15", "Q4 2026"),
    ("2027-04-15", "Q1 2027"),
    ("2027-06-15", "Q2 2027"),
    ("2027-09-15", "Q3 2027"),
    ("2028-01-18", "Q4 2027"),
)

INFLOW_KINDS = ("business", "paycheck", "side", "refund", "gift", "other")

# Share of what is left after tax + this month's essentials, by risk mode.
SPLITS = {
    "seed": {"fund": 0.70, "debt": 0.00, "invest": 0.00, "life": 0.20, "bet": 0.10},
    "measured": {"fund": 0.45, "debt": 0.15, "invest": 0.05, "life": 0.20, "bet": 0.15},
    "deploy": {"fund": 0.00, "debt": 0.15, "invest": 0.45, "life": 0.20, "bet": 0.20},
}

INSTRUMENTS = (
    {
        "id": "hysa",
        "name": "High-yield savings (HYSA)",
        "what": "FDIC-insured online savings. Top accounts pay about 4.0–4.35% APY vs a 0.64% national average.",
        "limit": "No contribution limit. FDIC covers $250,000 per bank, per owner.",
        "use_for": "Stability Fund and the tax bucket. Open two separate HYSAs so you never mix them.",
        "unlock": "always",
        "source": "https://www.bankrate.com/banking/savings/best-high-yield-interests-savings-accounts/",
    },
    {
        "id": "tax_bucket",
        "name": "Quarterly estimated tax (1040-ES)",
        "what": "Self-employed income has no withholding. You pay the IRS four times a year or owe penalties.",
        "limit": "Pay what you owe. Self-employment tax alone is 15.3% before income tax.",
        "use_for": "Every business deposit sends its tax slice here first.",
        "unlock": "self_employed",
        "source": "https://www.irs.gov/faqs/estimated-tax/individuals/individuals-2",
    },
    {
        "id": "debt_avalanche",
        "name": "High-interest debt payoff",
        "what": f"Paying a card at 22% APR is a guaranteed 22% return. Target anything at or above {DEBT_APR_THRESHOLD}% first.",
        "limit": "Highest APR first (avalanche).",
        "use_for": "Extra dollars once the fund is half full.",
        "unlock": "high_apr_debt",
        "source": "https://www.consumerfinance.gov/",
    },
    {
        "id": "roth_ira",
        "name": "Roth IRA",
        "what": "Money grows tax-free forever. Your contributions (not gains) can come back out anytime without penalty.",
        "limit": "2026: $7,500 ($8,600 at 50+). Phase-out $153k–$168k single, $242k–$252k married joint. 2026 contributions allowed until Apr 15, 2027.",
        "use_for": "First long-term account once the Stability Fund is half full.",
        "unlock": "fund_50",
        "source": "https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500",
    },
    {
        "id": "treasury_bills",
        "name": "Treasury bills",
        "what": "Short loans to the US government (4 to 52 weeks). Interest is free of state income tax.",
        "limit": "Buy $100+ at TreasuryDirect or any brokerage. Check today's rate before buying.",
        "use_for": "The part of the Stability Fund beyond 1 month of essentials, when T-bill rates beat your HYSA after state tax.",
        "unlock": "fund_50",
        "source": "https://www.treasurydirect.gov/marketable-securities/treasury-bills/",
    },
    {
        "id": "sep_ira",
        "name": "SEP IRA",
        "what": "Simple retirement account for the self-employed. One form, tax-deductible contributions.",
        "limit": "2026: up to 25% of net self-employment comp (about 20% for sole props), max $72,000.",
        "use_for": "Big tax deduction in strong business years after the fund is full.",
        "unlock": "fund_100_self_employed",
        "source": "https://www.irs.gov/retirement-plans/cola-increases-for-dollar-limitations-on-benefits-and-contributions",
    },
    {
        "id": "solo_401k",
        "name": "Solo 401(k)",
        "what": "For a business with no employees besides you (and a spouse). You contribute as both employee and employer.",
        "limit": "2026: $24,500 employee deferral + employer share, $72,000 combined. Catch-up $8,000 at 50+.",
        "use_for": "Shelters more than a SEP at modest income. Ask the provider about setup deadlines.",
        "unlock": "fund_100_self_employed",
        "source": "https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500",
    },
    {
        "id": "hsa",
        "name": "Health Savings Account (HSA)",
        "what": "Triple tax break: deductible in, tax-free growth, tax-free out for medical. Requires a high-deductible plan.",
        "limit": "2026: $4,400 self-only / $8,750 family (+$1,000 at 55+). HDHP deductible at least $1,700 / $3,400.",
        "use_for": "Only if your health plan is an HDHP.",
        "unlock": "hdhp",
        "source": "https://www.irs.gov/irb/2025-21_IRB",
    },
    {
        "id": "index_fund",
        "name": "Broad index fund (brokerage)",
        "what": "One fund that owns the whole market. Low fees, no picking stocks.",
        "limit": "No limit. Taxable account, so use after the Roth is maxed.",
        "use_for": "Long-term growth after Roth / SEP / Solo 401(k).",
        "unlock": "fund_100",
        "source": "https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-1",
    },
)


def _today() -> str:
    return datetime.now().date().isoformat()


def tax_rate_for(profile, override: float | None = None) -> dict[str, Any]:
    """Tax slice for business money. Self-employed gets a 25% floor (15.3% SE tax + income tax)."""
    if override is not None:
        return {"pct": float(override), "why": "Your custom rate for this deposit."}
    business = _loads(profile.business_budget_json, {})
    stated = float(business.get("tax_pct") or 0)
    if (profile.employment_type or "") == "self_employed" and stated < SELF_EMPLOYED_TAX_FLOOR:
        return {
            "pct": SELF_EMPLOYED_TAX_FLOOR,
            "why": f"Self-employed: 15.3% self-employment tax + income tax. Raised from {stated:g}% to {SELF_EMPLOYED_TAX_FLOOR:g}%.",
        }
    return {"pct": stated or 15.0, "why": "Your business budget tax rate."}


def next_tax_deadline(today: str | None = None) -> dict[str, Any]:
    today = today or _today()
    for due, label in TAX_DUE_DATES:
        if due >= today:
            days = (datetime.fromisoformat(due).date() - datetime.fromisoformat(today).date()).days
            return {"due": due, "label": label, "days_left": days, "form": "1040-ES"}
    return {"due": None, "label": "Check irs.gov", "days_left": None, "form": "1040-ES"}


def list_inflows(profile) -> list[dict[str, Any]]:
    return _loads(getattr(profile, "inflows_json", None), [])


def _month_totals(inflows: list[dict[str, Any]], month: str) -> dict[str, float]:
    totals = {"in": 0.0, "tax": 0.0, "essentials": 0.0, "fund": 0.0, "debt": 0.0, "invest": 0.0, "life": 0.0, "bet": 0.0}
    for flow in inflows:
        if not str(flow.get("date", "")).startswith(month):
            continue
        totals["in"] += float(flow.get("amount") or 0)
        for route in flow.get("routes", []):
            totals[route["key"]] = totals.get(route["key"], 0.0) + float(route.get("amount") or 0)
    return {k: _money(v) for k, v in totals.items()}


def _high_apr_debt(profile) -> dict[str, Any] | None:
    debts = [d for d in _loads(profile.debts_json, []) if isinstance(d, dict) and float(d.get("balance") or 0) > 0]
    hot = [d for d in debts if float(d.get("apr") or 0) >= DEBT_APR_THRESHOLD]
    return max(hot, key=lambda d: float(d.get("apr") or 0)) if hot else None


def _invest_destination(profile, ytd_roth: float) -> tuple[str, str]:
    annual = (profile.monthly_gross_income or 0) * 12
    if ytd_roth < 7500 and annual < 153_000:
        return "Roth IRA", f"${7500 - ytd_roth:,.0f} of 2026 Roth room left."
    if (profile.employment_type or "") == "self_employed":
        return "SEP IRA or Solo 401(k)", "Roth is full — shelter business income next."
    return "Broad index fund", "Tax-advantaged room is used — long-term brokerage next."


def route_inflow(
    profile,
    amount: float,
    *,
    source: str = "",
    kind: str = "business",
    date: str | None = None,
    tax_pct: float | None = None,
) -> dict[str, Any]:
    """Split one deposit into concrete moves. Never moves money — returns a checklist."""
    amount = _money(amount)
    date = date or _today()
    inflows = list_inflows(profile)
    month = _month_totals(inflows, date[:7])
    alloc = allocate_capital(profile)
    mode = alloc["mode"]
    fund_target = _money((profile.monthly_essentials or 0) * int(profile.stability_fund_target_months or 4))
    fund_gap = _money(max(0.0, fund_target - (profile.stability_fund_balance or 0)))
    routes: list[dict[str, Any]] = []
    left = amount

    def add(key, label, value, destination, why, instrument=None):
        nonlocal left
        value = _money(min(max(0.0, value), left))
        if value <= 0:
            return
        left = _money(left - value)
        same = next((r for r in routes if r["key"] == key), None)
        if same:
            same["amount"] = _money(same["amount"] + value)
            return
        routes.append(
            {"key": key, "label": label, "amount": value, "destination": destination,
             "why": why, "instrument": instrument, "done": False}
        )

    # Step 1: tax comes off business money before anything else.
    tax = tax_rate_for(profile, tax_pct)
    if kind in ("business", "side"):
        deadline = next_tax_deadline(date)
        add("tax", "Tax set-aside", amount * tax["pct"] / 100, "Tax HYSA (separate account)",
            f"{tax['pct']:g}% — {tax['why']} Next payment {deadline['label']} due {deadline['due']}.", "tax_bucket")

    # Step 2: cover what is still unpaid on this month's essentials.
    essentials_left = max(0.0, (profile.monthly_essentials or 0) - month["essentials"])
    add("essentials", "Bills this month", essentials_left, "Checking (bills account)",
        f"${essentials_left:,.0f} of ${profile.monthly_essentials or 0:,.0f} essentials still uncovered this month.")

    # Step 3: split the rest by risk mode.
    rest = left
    split = dict(SPLITS[mode])
    debt = _high_apr_debt(profile)
    if not debt:
        split["fund" if fund_gap > 0 else "invest"] += split.pop("debt")
    if fund_gap <= 0:
        split["invest"] += split.pop("fund", 0.0)
    risk_left = max(0.0, alloc["risk_budget"] - month["bet"])
    bet_share = min(rest * split.get("bet", 0), risk_left)
    overflow = rest * split.get("bet", 0) - bet_share
    split_amounts = {k: rest * v for k, v in split.items() if k != "bet"}
    split_amounts["fund" if fund_gap > 0 else "invest"] = split_amounts.get("fund" if fund_gap > 0 else "invest", 0) + overflow

    if split_amounts.get("fund"):
        add("fund", "Stability Fund", min(split_amounts["fund"], fund_gap), "Stability Fund HYSA",
            f"${fund_gap:,.0f} to go. Each dollar here raises your bet ceiling.", "hysa")
    if debt and split_amounts.get("debt"):
        add("debt", f"Extra payment: {debt.get('name', 'debt')}", split_amounts["debt"], debt.get("name", "Highest-APR debt"),
            f"{float(debt.get('apr') or 0):g}% APR — a guaranteed return.", "debt_avalanche")
    if split_amounts.get("invest"):
        ytd = sum(r["amount"] for f in inflows if str(f.get("date", ""))[:4] == date[:4]
                  for r in f.get("routes", []) if r["key"] == "invest" and r.get("done"))
        dest, why = _invest_destination(profile, ytd)
        add("invest", "Long-term", split_amounts["invest"], dest, why,
            "roth_ira" if dest == "Roth IRA" else ("sep_ira" if "SEP" in dest else "index_fund"))
    add("life", "Life (guilt-free)", split_amounts.get("life", 0), "Checking or spending card",
        "Spend it without guilt — that is how plans last.")
    add("bet", "Bet wallet", bet_share, "Separate bet account (never the fund)",
        f"${risk_left:,.0f} of ${alloc['risk_budget']:,.0f} monthly bet budget left. Underwrite before using.")

    # Step 4: anything still unassigned (caps hit) protects you first.
    if left > 0:
        fund_room = fund_gap - sum(r["amount"] for r in routes if r["key"] == "fund")
        add("fund", "Stability Fund", fund_room, "Stability Fund HYSA", "Leftover after caps — protect first.", "hysa")
        add("invest", "Long-term", left, "Broad index fund", "Leftover after caps and a full fund.", "index_fund")

    return {
        "inflow_id": uuid.uuid4().hex[:10],
        "date": date,
        "amount": amount,
        "source": source or "Deposit",
        "kind": kind,
        "mode": mode,
        "routes": routes,
        "created_at": _now_iso(),
    }


def save_inflow(profile, flow: dict[str, Any]) -> list[dict[str, Any]]:
    inflows = list_inflows(profile)
    inflows.append(flow)
    profile.inflows_json = json.dumps(inflows[-400:])
    return inflows


def mark_route_done(profile, inflow_id: str, key: str) -> dict[str, Any] | None:
    """User confirms they moved the money. Fund and invest routes update balances."""
    inflows = list_inflows(profile)
    for flow in inflows:
        if flow.get("inflow_id") != inflow_id:
            continue
        for route in flow.get("routes", []):
            if route["key"] != key or route.get("done"):
                continue
            route["done"] = True
            route["done_at"] = _now_iso()
            if key == "fund":
                profile.stability_fund_balance = _money((profile.stability_fund_balance or 0) + route["amount"])
            elif key == "invest":
                state = _loads(profile.wealth_state_json, {})
                state["investments"] = _money(float(state.get("investments") or 0) + route["amount"])
                profile.wealth_state_json = json.dumps(state)
            profile.inflows_json = json.dumps(inflows)
            return flow
    return None


def toolbox(profile) -> list[dict[str, Any]]:
    """Accounts that fit right now, what unlocks next, and what is not yet."""
    alloc = allocate_capital(profile)
    pct = alloc["stability_fund_pct"]
    self_employed = (profile.employment_type or "") == "self_employed"
    checks = {
        "always": (True, ""),
        "self_employed": (self_employed, "Applies to self-employed income."),
        "high_apr_debt": (_high_apr_debt(profile) is not None, f"No debt at or above {DEBT_APR_THRESHOLD}% APR."),
        "fund_50": (pct >= 50, f"Unlocks when the Stability Fund hits 50% (now {pct:g}%)."),
        "fund_100": (pct >= 100, f"Unlocks when the Stability Fund hits 100% (now {pct:g}%)."),
        "fund_100_self_employed": (pct >= 100 and self_employed, f"Self-employed + Stability Fund at 100% (now {pct:g}%)."),
        "hdhp": (False, "Only if your health plan is a high-deductible plan (HDHP)."),
    }
    out = []
    for item in INSTRUMENTS:
        ok, reason = checks[item["unlock"]]
        if item["unlock"] == "hdhp":
            status = "check"
        elif ok:
            status = "now"
        elif item["unlock"] in ("fund_50",) or (item["unlock"].startswith("fund_100") and pct >= 50):
            status = "next"
        else:
            status = "later"
        out.append({**item, "status": status, "gate": reason, "researched_on": RESEARCHED_ON})
    return out


def today_payload(profile) -> dict[str, Any]:
    today = _today()
    inflows = list_inflows(profile)
    open_routes = [
        {**r, "inflow_id": f["inflow_id"], "source": f.get("source"), "date": f.get("date")}
        for f in inflows for r in f.get("routes", []) if not r.get("done")
    ]
    alloc = allocate_capital(profile)
    month = _month_totals(inflows, today[:7])
    return {
        "date": today,
        "today": [f for f in inflows if f.get("date") == today],
        "recent": list(reversed(inflows[-8:])),
        "open_routes": open_routes,
        "month": month,
        "month_target": {"income": _money(profile.monthly_gross_income), "essentials": _money(profile.monthly_essentials)},
        "risk": {"budget": alloc["risk_budget"], "used": month["bet"], "left": _money(max(0, alloc["risk_budget"] - month["bet"]))},
        "mode": alloc["mode"],
        "fund_pct": alloc["stability_fund_pct"],
        "tax": {**tax_rate_for(profile), "next": next_tax_deadline(today)},
        "toolbox": toolbox(profile),
        "kinds": list(INFLOW_KINDS),
    }
