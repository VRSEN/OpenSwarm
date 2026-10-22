"""Tests for structured income, expense, and bill parsing."""

import json

from backend.services.financial_profile import (
    build_expense_breakdown,
    build_income_breakdown,
    parse_bills,
    parse_expenses,
    parse_income_streams,
    sync_headline_totals,
    total_expenses,
    total_monthly_income,
)


class _Profile:
    monthly_gross_income = 0
    monthly_essentials = 0
    income_streams_json = None
    expenses_json = None
    bills_json = None


def test_parse_income_streams_and_total():
    raw = [
        {"name": "W-2", "source_type": "w2", "amount_monthly": 3000},
        {"name": "Clients", "source_type": "business", "amount_monthly": 4500},
    ]
    streams = parse_income_streams(raw)
    assert len(streams) == 2
    assert total_monthly_income(streams) == 7500


def test_parse_expenses_and_bills_total():
    expenses = parse_expenses({"housing": 1200, "food_groceries": 600})
    bills = parse_bills([{"name": "Netflix", "amount_monthly": 15}])
    assert total_expenses(expenses, bills) == 1815


def test_sync_headline_totals_updates_profile():
    p = _Profile()
    p.income_streams_json = json.dumps([{"name": "Biz", "amount_monthly": 5000}])
    p.expenses_json = json.dumps({"housing": 1500, "utilities": 200})
    p.bills_json = json.dumps([{"name": "Phone", "amount_monthly": 80}])
    sync_headline_totals(p)
    assert p.monthly_gross_income == 5000
    assert p.monthly_essentials == 1780


def test_build_breakdowns_from_structured_data():
    p = _Profile()
    p.monthly_gross_income = 0
    p.income_streams_json = json.dumps([{"name": "Retainers", "source_type": "business", "amount_monthly": 6000}])
    p.expenses_json = json.dumps({"housing": 1400})
    p.bills_json = json.dumps([{"name": "Insurance", "amount_monthly": 120}])
    income = build_income_breakdown(p)
    expense = build_expense_breakdown(p)
    assert income["total_monthly"] == 6000
    assert expense["total_monthly"] == 1520
    assert expense["bills_total"] == 120
