"""Structured income, expenses, bills — totals sync to profile headline fields."""

from __future__ import annotations

import json
from typing import Any

INCOME_SOURCE_TYPES = ("w2", "business", "contract", "passive", "gig", "other")
EXPENSE_CATEGORIES = (
    "housing",
    "utilities",
    "food_groceries",
    "transportation",
    "insurance",
    "healthcare",
    "childcare",
    "personal",
    "business_opex",
    "debt_minimums",
    "other",
)
DEBT_TYPES = (
    "credit_card",
    "auto",
    "student",
    "mortgage",
    "medical",
    "personal",
    "collections",
    "other",
)

CATEGORY_LABELS = {
    "housing": "Housing (rent/mortgage)",
    "utilities": "Utilities & phone",
    "food_groceries": "Food & groceries",
    "transportation": "Transportation & gas",
    "insurance": "Insurance (non-health)",
    "healthcare": "Healthcare & meds",
    "childcare": "Childcare & dependents",
    "personal": "Personal / household",
    "business_opex": "Business costs (personal account)",
    "debt_minimums": "Debt minimum payments",
    "other": "Other essentials",
}


def _loads(raw: str | list | dict | None, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw or "")
    except json.JSONDecodeError:
        return default


def parse_income_streams(raw: str | list | None) -> list[dict[str, Any]]:
    streams = _loads(raw, [])
    if not isinstance(streams, list):
        return []
    out = []
    for item in streams:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        amount = float(item.get("amount_monthly") or 0)
        if not name and amount <= 0:
            continue
        out.append(
            {
                "name": name or "Income",
                "source_type": item.get("source_type") or "other",
                "amount_monthly": round(amount, 2),
                "frequency": item.get("frequency") or "monthly",
                "notes": (item.get("notes") or "").strip(),
            }
        )
    return out


def total_monthly_income(streams: list[dict]) -> float:
    return round(sum(float(s.get("amount_monthly") or 0) for s in streams), 2)


def parse_expenses(raw: str | dict | None) -> dict[str, float]:
    data = _loads(raw, {})
    if not isinstance(data, dict):
        return {k: 0.0 for k in EXPENSE_CATEGORIES}
    return {k: round(float(data.get(k) or 0), 2) for k in EXPENSE_CATEGORIES}


def parse_bills(raw: str | list | None) -> list[dict[str, Any]]:
    bills = _loads(raw, [])
    if not isinstance(bills, list):
        return []
    out = []
    for item in bills:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        amount = float(item.get("amount_monthly") or 0)
        if not name and amount <= 0:
            continue
        out.append(
            {
                "name": name or "Bill",
                "amount_monthly": round(amount, 2),
                "due_day": int(item.get("due_day") or 0),
                "category": item.get("category") or "other",
                "autopay": bool(item.get("autopay", False)),
            }
        )
    return out


def total_bills(bills: list[dict]) -> float:
    return round(sum(float(b.get("amount_monthly") or 0) for b in bills), 2)


def total_expenses(expenses: dict[str, float], bills: list[dict] | None = None) -> float:
    base = sum(expenses.values())
    bill_total = total_bills(bills or [])
    # Avoid double-count if user put subscriptions in both — bills are additive to categories
    return round(base + bill_total, 2)


def parse_collections(raw: str | list | None) -> list[dict[str, Any]]:
    items = _loads(raw, [])
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        creditor = (item.get("creditor") or item.get("name") or "").strip()
        balance = float(item.get("balance") or 0)
        if not creditor and balance <= 0:
            continue
        out.append(
            {
                "creditor": creditor or "Collection",
                "balance": round(balance, 2),
                "status": item.get("status") or "open",
                "notes": (item.get("notes") or "").strip(),
            }
        )
    return out


def collections_total(items: list[dict]) -> float:
    return round(sum(float(i.get("balance") or 0) for i in items), 2)


def sync_headline_totals(profile) -> None:
    """Derive monthly_gross_income and monthly_essentials from structured data when present."""
    streams = parse_income_streams(getattr(profile, "income_streams_json", None))
    if streams:
        profile.monthly_gross_income = total_monthly_income(streams)

    expenses = parse_expenses(getattr(profile, "expenses_json", None))
    bills = parse_bills(getattr(profile, "bills_json", None))
    expense_total = total_expenses(expenses, bills)
    if expense_total > 0:
        profile.monthly_essentials = expense_total


def build_income_breakdown(profile) -> dict[str, Any]:
    streams = parse_income_streams(getattr(profile, "income_streams_json", None))
    if not streams and (profile.monthly_gross_income or 0) > 0:
        streams = [
            {
                "name": "Business / primary income",
                "source_type": "business",
                "amount_monthly": profile.monthly_gross_income,
                "frequency": "monthly",
                "notes": "",
            }
        ]
    return {
        "streams": streams,
        "total_monthly": total_monthly_income(streams) or profile.monthly_gross_income or 0,
    }


def build_expense_breakdown(profile) -> dict[str, Any]:
    expenses = parse_expenses(getattr(profile, "expenses_json", None))
    bills = parse_bills(getattr(profile, "bills_json", None))
    by_category = {CATEGORY_LABELS[k]: expenses.get(k, 0) for k in EXPENSE_CATEGORIES if expenses.get(k, 0) > 0}
    total = total_expenses(expenses, bills)
    if total <= 0:
        total = profile.monthly_essentials or 0
    return {
        "categories": expenses,
        "category_labels": CATEGORY_LABELS,
        "by_category_labeled": by_category,
        "bills": bills,
        "bills_total": total_bills(bills),
        "total_monthly": total,
    }


def serialize_intake_data(profile) -> dict[str, Any]:
    """Full intake payload for UI edit forms."""
    credit = _loads(profile.credit_snapshot_json, {})
    collections = parse_collections(credit.get("collections_items"))
    return {
        "display_name": profile.display_name,
        "primary_trade": profile.primary_trade,
        "employment_type": profile.employment_type or "self_employed",
        "cashflow_quadrant_primary": profile.cashflow_quadrant_primary or "S",
        "income_mix": _loads(profile.cashflow_quadrant_json, {}),
        "income_streams": build_income_breakdown(profile)["streams"],
        "monthly_gross_income": profile.monthly_gross_income or 0,
        "expenses": parse_expenses(profile.expenses_json),
        "bills": parse_bills(profile.bills_json),
        "monthly_essentials": profile.monthly_essentials or 0,
        "stability_fund_balance": profile.stability_fund_balance or 0,
        "stability_fund_target_months": profile.stability_fund_target_months or 4,
        "debts": _loads(profile.debts_json, []),
        "credit": credit,
        "collections_items": collections,
        "business_budget": _loads(profile.business_budget_json, {}),
        "footprints": _loads(profile.footprints_json, {}),
        "intake_step": profile.intake_step or 0,
        "intake_completed": profile.intake_completed_at is not None,
    }
