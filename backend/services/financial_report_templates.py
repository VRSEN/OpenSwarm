"""Financial report templates — render Markdown and HTML from intake summary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

REPORT_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "financial_snapshot",
        "name": "Financial Snapshot",
        "description": "One-page overview: income, 15/65/20, Stability Fund, debt, credit, ESBI.",
    },
    {
        "id": "debt_action_plan",
        "name": "Debt Action Plan",
        "description": "Debt totals, snowball order, and weekly payoff actions.",
    },
    {
        "id": "cash_flow_brief",
        "name": "Cash Flow Brief",
        "description": "15/65/20 allocation, Profit First buckets, and monthly gap.",
    },
    {
        "id": "architect_status",
        "name": "Architect Status Report",
        "description": "Executive summary: stage, ESBI path, next mechanical moves, full picture.",
    },
]

_TEMPLATE_IDS = {t["id"] for t in REPORT_TEMPLATES}


def list_report_templates() -> list[dict[str, str]]:
    return list(REPORT_TEMPLATES)


def _money(value: float | int | None) -> str:
    n = float(value or 0)
    return f"${n:,.0f}" if abs(n - round(n)) < 0.01 else f"${n:,.2f}"


def _pct(value: float | int | None) -> str:
    return f"{float(value or 0):.1f}%"


def _report_date() -> str:
    return datetime.now(timezone.utc).strftime("%B %d, %Y")


def render_report_markdown(
    template_id: str,
    summary: dict[str, Any],
    journey: dict[str, Any] | None = None,
) -> str:
    if template_id not in _TEMPLATE_IDS:
        raise ValueError(f"Unknown template: {template_id}")

    journey = journey or {}
    name = summary.get("display_name") or "Architect"
    trade = summary.get("primary_trade") or "Self-employed operator"
    date = _report_date()
    disclaimer = summary.get("disclaimer", "")

    if template_id == "financial_snapshot":
        return _markdown_snapshot(name, trade, date, summary, journey, disclaimer)
    if template_id == "debt_action_plan":
        return _markdown_debt_plan(name, trade, date, summary, disclaimer)
    if template_id == "cash_flow_brief":
        return _markdown_cash_flow(name, trade, date, summary, disclaimer)
    return _markdown_architect_status(name, trade, date, summary, journey, disclaimer)


def render_report_html(
    template_id: str,
    summary: dict[str, Any],
    journey: dict[str, Any] | None = None,
) -> str:
    md = render_report_markdown(template_id, summary, journey)
    return _markdown_to_styled_html(md, summary.get("display_name") or "Architect")


def _section(title: str, lines: list[str]) -> str:
    body = "\n".join(lines)
    return f"## {title}\n\n{body}\n"


def _markdown_income_breakdown(summary: dict[str, Any]) -> list[str]:
    income = summary.get("income_breakdown") or {}
    streams = income.get("streams") or []
    if not streams:
        return [
            f"- Total monthly income: **{_money(summary.get('monthly_gross_income'))}** (single headline — add streams in intake Step 2 for detail)"
        ]
    lines = [f"- **Total monthly income: {_money(income.get('total_monthly') or summary.get('monthly_gross_income'))}**"]
    for s in streams:
        stype = (s.get("source_type") or "other").replace("_", " ")
        lines.append(f"- {s.get('name', 'Income')} ({stype}): **{_money(s.get('amount_monthly'))}**/mo")
        if s.get("notes"):
            lines.append(f"  - _{s['notes']}_")
    return lines


def _markdown_expense_breakdown(summary: dict[str, Any]) -> list[str]:
    expense = summary.get("expense_breakdown") or {}
    labeled = expense.get("by_category_labeled") or {}
    bills = expense.get("bills") or []
    if not labeled and not bills:
        return [f"- Total monthly essentials: **{_money(summary.get('monthly_essentials'))}**"]
    lines = [f"- **Total monthly essentials: {_money(expense.get('total_monthly') or summary.get('monthly_essentials'))}**"]
    for label, amount in labeled.items():
        lines.append(f"- {label}: **{_money(amount)}**")
    if bills:
        lines.append(f"- Recurring bills subtotal: **{_money(expense.get('bills_total'))}**")
        for b in bills:
            due = f", due day {b['due_day']}" if b.get("due_day") else ""
            autopay = " · autopay" if b.get("autopay") else ""
            lines.append(f"  - {b.get('name', 'Bill')}: **{_money(b.get('amount_monthly'))}**/mo{due}{autopay}")
    return lines


def _markdown_credit_detail(summary: dict[str, Any]) -> list[str]:
    credit = summary.get("credit_plan") or {}
    snap = summary.get("credit_snapshot") or {}
    items = credit.get("collections_items") or snap.get("collections_items") or []
    lines = [
        f"- Score band: **{credit.get('score_band', snap.get('score_band', 'unknown'))}**",
        f"- Estimated score: **{snap.get('estimated_score') or credit.get('estimated_score_midpoint', '—')}**",
        f"- Utilization: **{_pct(credit.get('utilization_pct', snap.get('utilization_pct')))}**",
        f"- Total credit limits: **{_money(snap.get('total_credit_limit'))}**",
        f"- Revolving balances: **{_money(snap.get('total_revolver_balance'))}**",
        f"- Loan readiness: **{credit.get('loan_readiness_score', '—')}/100**",
    ]
    if credit.get("collections_balance") or items:
        lines.append(
            f"- Collections: **{_money(credit.get('collections_balance'))}** "
            f"({credit.get('collections_count') or len(items)} account(s))"
        )
    charge_offs = credit.get("charge_offs") or snap.get("charge_offs") or 0
    bankruptcies = credit.get("bankruptcies") or snap.get("bankruptcies") or 0
    inquiries = credit.get("inquiries_6mo") or snap.get("inquiries_6mo") or 0
    if charge_offs:
        lines.append(f"- Charge-offs: **{charge_offs}**")
    if bankruptcies:
        lines.append(f"- Bankruptcies: **{bankruptcies}**")
    if inquiries:
        lines.append(f"- Hard inquiries (6 mo): **{inquiries}**")
    if credit.get("late_payments_12mo") or snap.get("late_payments_12mo"):
        lines.append("- Late payments in last 12 months: **Yes**")
    for item in items:
        lines.append(
            f"  - {item.get('creditor', 'Collection')}: **{_money(item.get('balance'))}** ({item.get('status', 'open')})"
        )
    for flag in credit.get("flags") or []:
        lines.append(f"- ⚠ {flag}")
    for action in credit.get("weekly_actions") or []:
        lines.append(f"- Action: {action}")
    return lines


def _markdown_debt_lines(debts: list[dict]) -> list[str]:
    if not debts:
        return ["- No debts on file."]
    lines = []
    for d in debts:
        extra = []
        if d.get("debt_type"):
            extra.append(d["debt_type"].replace("_", " "))
        if d.get("in_collections"):
            extra.append("in collections")
        if float(d.get("past_due_amount") or 0) > 0:
            extra.append(f"past due {_money(d['past_due_amount'])}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(
            f"- **{d.get('name', 'Debt')}**: {_money(d.get('balance'))} @ {_pct(d.get('apr'))} APR "
            f"(min {_money(d.get('minimum_payment'))}){suffix}"
        )
    return lines


def _markdown_snapshot(
    name: str,
    trade: str,
    date: str,
    summary: dict[str, Any],
    journey: dict[str, Any],
    disclaimer: str,
) -> str:
    alloc = summary.get("allocation_156520") or {}
    stability = summary.get("stability_fund") or {}
    cq = summary.get("cashflow_quadrant") or {}

    lines = [
        f"# Financial Snapshot — {name}",
        f"**Prepared:** {date}  ",
        f"**Trade / business:** {trade}  ",
        f"**Data source:** {summary.get('data_source_badge', 'Your data')}  ",
        "",
        _section(
            "Income & essentials",
            [
                *_markdown_income_breakdown(summary),
                f"- Monthly gap (income − essentials): **{_money((summary.get('monthly_gross_income') or 0) - (summary.get('monthly_essentials') or 0))}**",
            ],
        ).strip(),
        _section("Expense breakdown", _markdown_expense_breakdown(summary)).strip(),
        _section(
            "15 / 65 / 20 allocation (target)",
            [
                f"- Future (15%): **{_money(alloc.get('future'))}**",
                f"- Essentials (65%): **{_money(alloc.get('essentials'))}**",
                f"- Life (20%): **{_money(alloc.get('life'))}**",
            ],
        ).strip(),
        _section(
            "Stability Fund",
            [
                f"- Balance: **{_money(stability.get('balance'))}**",
                f"- Target ({stability.get('target_months', 4)} months): **{_money(stability.get('target'))}**",
                f"- Progress: **{_pct(stability.get('pct_of_target'))}**",
                f"- Gap remaining: **{_money(stability.get('gap_remaining'))}**",
            ],
        ).strip(),
        _section(
            "Debt & credit",
            [
                f"- Total debt: **{_money(summary.get('debt_total'))}**",
                f"- Snowball focus: **{summary.get('debt_snowball', {}).get('primary_target') or 'None on file'}**",
                *_markdown_credit_detail(summary),
            ],
        ).strip(),
        _section(
            "Wealth stage & ESBI",
            [
                f"- Stage: **{journey.get('stage', 'Stability')}** — {journey.get('stage_description', '')}",
                f"- Next action: {journey.get('next_mechanical_action', 'Fund Stability Fund.')}",
                f"- Cashflow quadrant: **{cq.get('badge', '—')}** ({cq.get('primary_label', '')} → {cq.get('target_label', '')})",
            ],
        ).strip(),
        f"---\n\n*{disclaimer}*",
    ]
    return "\n\n".join(lines)


def _markdown_debt_plan(
    name: str,
    trade: str,
    date: str,
    summary: dict[str, Any],
    disclaimer: str,
) -> str:
    snowball = summary.get("debt_snowball") or {}
    debts = summary.get("debts") or []
    debt_lines = _markdown_debt_lines(debts)

    plan_lines = []
    for step in snowball.get("snowball_plan") or []:
        pay = step.get("suggested_extra_payment") or step.get("payment") or 0
        plan_lines.append(
            f"- Pay **{_money(pay)}** toward {step.get('name')} "
            f"({_pct(step.get('apr'))} APR)"
        )
    if not plan_lines:
        plan_lines.append(f"- {snowball.get('message', 'Review debt strategy with advisor.')}")

    actions = snowball.get("weekly_actions") or (summary.get("credit_plan") or {}).get("weekly_actions") or []
    action_lines = [f"- {a}" for a in actions] or ["- Maintain on-time payments."]

    return "\n\n".join(
        [
            f"# Debt Action Plan — {name}",
            f"**Prepared:** {date}  ",
            f"**Trade / business:** {trade}  ",
            "",
            _section("Summary", [
                f"- Total debt balance: **{_money(summary.get('debt_total'))}**",
                f"- Verdict: **{snowball.get('verdict', 'review')}**",
                f"- Primary snowball target: **{snowball.get('primary_target') or '—'}**",
                f"- Rule: {snowball.get('rule', 'High APR first, then roll payments.')}",
            ]).strip(),
            _section("Debts on file", debt_lines).strip(),
            _section("Recommended payoff order", plan_lines).strip(),
            _section("Credit & collections", _markdown_credit_detail(summary)).strip(),
            _section("Actions this week", action_lines).strip(),
            f"---\n\n*{disclaimer}*",
        ]
    )


def _markdown_cash_flow(
    name: str,
    trade: str,
    date: str,
    summary: dict[str, Any],
    disclaimer: str,
) -> str:
    alloc = summary.get("allocation_156520") or {}
    pf = summary.get("profit_first") or {}
    business = summary.get("business_budget") or {}
    revenue = summary.get("monthly_gross_income") or 0
    essentials = summary.get("monthly_essentials") or 0

    pf_lines = ["- Profit First breakdown not on file — complete intake Step 5."]
    if pf and not pf.get("error"):
        buckets = pf.get("allocations") or {}
        pcts = pf.get("percentages") or business
        pf_lines = [
            f"- Monthly business revenue: **{_money(pf.get('gross_revenue') or business.get('monthly_revenue') or revenue)}**",
            f"- Profit ({pcts.get('profit', business.get('profit_pct', 5))}%): **{_money(buckets.get('profit'))}**",
            f"- Tax ({pcts.get('tax', business.get('tax_pct', 15))}%): **{_money(buckets.get('tax'))}**",
            f"- Owner pay ({pcts.get('owner_pay', business.get('owner_pay_pct', 50))}%): **{_money(buckets.get('owner_pay'))}**",
            f"- OpEx ({pcts.get('opex', business.get('opex_pct', 30))}%): **{_money(buckets.get('opex'))}**",
        ]

    return "\n\n".join(
        [
            f"# Cash Flow Brief — {name}",
            f"**Prepared:** {date}  ",
            f"**Trade / business:** {trade}  ",
            "",
            _section(
                "Monthly picture",
                [
                    *_markdown_income_breakdown(summary),
                    *_markdown_expense_breakdown(summary),
                    f"- Surplus before allocation: **{_money(revenue - essentials)}**",
                ],
            ).strip(),
            _section(
                "15 / 65 / 20 (dollar targets)",
                [
                    f"- Future bucket (15%): **{_money(alloc.get('future'))}** — debt snowball, Stability Fund, investments",
                    f"- Essentials bucket (65%): **{_money(alloc.get('essentials'))}**",
                    f"- Life bucket (20%): **{_money(alloc.get('life'))}**",
                ],
            ).strip(),
            _section("Profit First (business buckets)", pf_lines).strip(),
            _section(
                "Operator notes",
                [
                    "- Fund **Tax** and **Stability Fund** before aggressive investing.",
                    "- Side-hustle + W-2: track employee income separately in ESBI mix.",
                    "- Re-run intake when revenue shifts materially.",
                ],
            ).strip(),
            f"---\n\n*{disclaimer}*",
        ]
    )


def _markdown_architect_status(
    name: str,
    trade: str,
    date: str,
    summary: dict[str, Any],
    journey: dict[str, Any],
    disclaimer: str,
) -> str:
    cq = summary.get("cashflow_quadrant") or {}
    mix = cq.get("income_mix_pct") or {}
    stability = summary.get("stability_fund") or {}

    return "\n\n".join(
        [
            f"# Architect Status Report — {name}",
            f"**Prepared:** {date}  ",
            f"**Trade / business:** {trade}  ",
            f"**Employment type:** {summary.get('employment_type', 'self_employed')}  ",
            "",
            _section(
                "Executive summary",
                [
                    f"- **Stage:** {journey.get('stage', 'Stability')} ({journey.get('stage_index', 1)}/{journey.get('total_stages', 5)})",
                    f"- **Next mechanical action:** {journey.get('next_mechanical_action', 'Fund Stability Fund.')}",
                    f"- **Monthly income:** {_money(summary.get('monthly_gross_income'))} | **Essentials:** {_money(summary.get('monthly_essentials'))}",
                    f"- **Stability Fund:** {_pct(stability.get('pct_of_target'))} of target",
                    f"- **Total debt:** {_money(summary.get('debt_total'))}",
                ],
            ).strip(),
            _section("Income detail", _markdown_income_breakdown(summary)).strip(),
            _section("Expense detail", _markdown_expense_breakdown(summary)).strip(),
            _section(
                "Cashflow Quadrant (ESBI)",
                [
                    f"- Badge: **{cq.get('badge', '—')}**",
                    f"- Primary: {cq.get('primary_label', '—')} — {cq.get('primary_description', '')}",
                    f"- Target: {cq.get('target_label', '—')}",
                    f"- Income mix: E {_pct(mix.get('E'))} | S {_pct(mix.get('S'))} | B {_pct(mix.get('B'))} | I {_pct(mix.get('I'))}",
                    f"- Next ESBI move: {cq.get('next_mechanical_move', '')}",
                ],
            ).strip(),
            _section(
                "Credit & readiness",
                _markdown_credit_detail(summary),
            ).strip(),
            _section(
                "30-day priorities",
                [
                    "1. Hit next mechanical action for current stage.",
                    "2. Execute top debt or Stability Fund move from intake.",
                    "3. Track one weekly promise on Integrity Engine.",
                ],
            ).strip(),
            f"---\n\n*{disclaimer}*",
        ]
    )


def _markdown_to_styled_html(markdown: str, title: str) -> str:
    """Simple Markdown → HTML for reports (headings, bullets, bold, hr)."""
    lines = markdown.split("\n")
    body: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.strip()
        if not line:
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            body.append(f"<h1>{_inline_md(line[2:])}</h1>")
        elif line.startswith("## "):
            close_list()
            body.append(f"<h2>{_inline_md(line[3:])}</h2>")
        elif line.startswith("---"):
            close_list()
            body.append("<hr />")
        elif line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_inline_md(line[2:])}</li>")
        elif line.startswith("*") and line.endswith("*") and not line.startswith("**"):
            close_list()
            body.append(f"<p class='disclaimer'>{_inline_md(line.strip('*'))}</p>")
        else:
            close_list()
            body.append(f"<p>{_inline_md(line)}</p>")

    close_list()
    content = "\n".join(body)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{_escape(title)} — Financial Report</title>
  <style>
    @page {{ size: letter; margin: 0.75in; }}
    body {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 11pt;
      line-height: 1.55;
      color: #1a1a1a;
      max-width: 7.5in;
      margin: 0 auto;
    }}
    h1 {{
      font-family: Arial, Helvetica, sans-serif;
      font-size: 22pt;
      color: #0d3b2e;
      border-bottom: 3px solid #2ecc71;
      padding-bottom: 0.35rem;
      margin-bottom: 0.75rem;
    }}
    h2 {{
      font-family: Arial, Helvetica, sans-serif;
      font-size: 13pt;
      color: #145a32;
      margin-top: 1.25rem;
      margin-bottom: 0.5rem;
    }}
    ul {{ margin: 0.25rem 0 0.75rem 1.25rem; padding: 0; }}
    li {{ margin-bottom: 0.35rem; }}
    hr {{ border: none; border-top: 1px solid #ccc; margin: 1.5rem 0; }}
    .disclaimer {{ font-size: 9pt; color: #666; font-style: italic; }}
    strong {{ color: #0d3b2e; }}
  </style>
</head>
<body>
{content}
</body>
</html>"""


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _inline_md(text: str) -> str:
    import re

    escaped = _escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped
