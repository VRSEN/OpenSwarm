import pytest

from backend.services.financial_intake import (
    build_financial_summary,
    compute_156520,
    compute_credit_indicators,
    compute_debt_snowball,
    compute_profit_first,
    compute_stability_gap,
)


def test_156520_split():
    split = compute_156520(10000)
    assert split["future"] == 1500
    assert split["essentials"] == 6500
    assert split["life"] == 2000


def test_stability_gap():
    gap = compute_stability_gap(3000, 6000, 4)
    assert gap["target"] == 12000
    assert gap["pct_of_target"] == 50.0


def test_debt_snowball_orders_by_apr():
    debts = [
        {"name": "Car", "balance": 8000, "apr": 5.1, "minimum_payment": 310},
        {"name": "Card", "balance": 4200, "apr": 9.2, "minimum_payment": 120},
    ]
    result = compute_debt_snowball(debts, available_surplus=400)
    assert result["verdict"] == "execute"
    assert result["primary_target"] == "Card"


def test_credit_indicators_flags_utilization():
    plan = compute_credit_indicators({"score_band": "fair", "utilization_pct": 45, "late_payments_12mo": True})
    assert plan["loan_readiness_score"] < 70
    assert len(plan["flags"]) >= 2


def test_profit_first_must_sum_100():
    ok = compute_profit_first(8000)
    assert "allocations" in ok
    bad = compute_profit_first(8000, profit_pct=10, tax_pct=10, owner_pay_pct=10, opex_pct=10)
    assert "error" in bad


class _FakeProfile:
    user_id = "test"
    display_name = "Alex"
    primary_trade = "Consulting"
    employment_type = "self_employed"
    monthly_gross_income = 8000
    monthly_essentials = 5200
    stability_fund_balance = 4000
    stability_fund_target_months = 4
    data_source = "manual"
    intake_completed_at = True
    debts_json = '[{"name": "Visa", "balance": 3000, "apr": 18, "minimum_payment": 90}]'
    credit_snapshot_json = '{"score_band": "fair", "utilization_pct": 35}'
    business_budget_json = '{"monthly_revenue": 8000, "profit_pct": 5, "tax_pct": 15, "owner_pay_pct": 50, "opex_pct": 30}'
    revenue_per_hour = 0
    baseline_revenue_per_hour = 0


def test_build_financial_summary_uses_manual_source():
    summary = build_financial_summary(_FakeProfile())
    assert summary["data_source"] == "manual"
    assert summary["data_source_badge"] == "Your data"
    assert summary["monthly_gross_income"] == 8000
    assert summary["debt_snowball"]["primary_target"] == "Visa"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from backend.app import create_mechanical_app

    app = create_mechanical_app()
    with TestClient(app) as c:
        yield c


def test_intake_flow_end_to_end(client):
    r = client.post("/user/intake/step/1", json={"display_name": "Alex", "primary_trade": "HVAC", "employment_type": "business_owner"})
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/2",
        json={
            "monthly_gross_income": 6500,
            "monthly_essentials": 4200,
            "stability_fund_balance": 2000,
            "stability_fund_target_months": 4,
        },
    )
    assert r.status_code == 200
    assert r.json()["preview"]["allocation_156520"]["future"] == pytest.approx(975, rel=0.01)

    r = client.post(
        "/user/intake/step/3",
        json={"debts": [{"name": "Card", "balance": 1500, "apr": 22, "minimum_payment": 50}]},
    )
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/4",
        json={"score_band": "fair", "utilization_pct": 40, "late_payments_12mo": False, "collections": False},
    )
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/5",
        json={
            "business_type": "LLC",
            "monthly_revenue": 6500,
            "profit_pct": 5,
            "tax_pct": 15,
            "owner_pay_pct": 50,
            "opex_pct": 30,
        },
    )
    assert r.status_code == 200

    r = client.post("/user/intake/complete", json={"display_name": "Alex", "focus_season_months": 6})
    assert r.status_code == 200
    assert r.json()["intake_completed"] is True

    summary = client.get("/user/intake/summary").json()
    assert summary["data_source"] == "manual"
    assert summary["monthly_gross_income"] == 6500

    missions = client.get("/mirror/dollar-missions").json()
    assert missions["missions"][0]["amount"] == pytest.approx(975, rel=0.01)

    credit = client.get("/user/intake/credit-plan").json()
    assert "credit_plan" in credit

    wins = client.get("/user/intake/quick-wins").json()
    assert len(wins["quick_wins"]) >= 1

    modules = client.get("/literacy/modules").json()
    assert len(modules["modules"]) >= 9


def test_structured_intake_flow(client):
    """New 8-step intake with income streams, expenses, bills, and collections."""
    client.post("/user/intake/reset")
    r = client.post("/user/intake/step/1", json={"display_name": "Riley", "primary_trade": "Plumbing", "employment_type": "self_employed"})
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/2",
        json={
            "income_streams": [
                {"name": "Service calls", "source_type": "business", "amount_monthly": 5500},
                {"name": "W-2 spouse", "source_type": "w2", "amount_monthly": 2000},
            ]
        },
    )
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/3",
        json={"housing": 1400, "utilities": 250, "food_groceries": 700, "transportation": 400},
    )
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/4",
        json={
            "bills": [{"name": "Car insurance", "amount_monthly": 120, "due_day": 15, "category": "insurance"}],
            "stability_fund_balance": 3000,
            "stability_fund_target_months": 4,
        },
    )
    assert r.status_code == 200
    assert r.json()["preview"]["monthly_gross_income"] == 7500

    r = client.post(
        "/user/intake/step/5",
        json={"debts": [{"name": "Visa", "balance": 2200, "apr": 19.9, "minimum_payment": 65, "debt_type": "credit_card"}]},
    )
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/6",
        json={
            "score_band": "fair",
            "estimated_score": 670,
            "utilization_pct": 38,
            "collections_items": [{"creditor": "Medical collections", "balance": 450, "status": "open"}],
            "collections": True,
        },
    )
    assert r.status_code == 200

    r = client.post(
        "/user/intake/step/7",
        json={"monthly_revenue": 5500, "profit_pct": 5, "tax_pct": 15, "owner_pay_pct": 50, "opex_pct": 30},
    )
    assert r.status_code == 200

    r = client.post("/user/intake/step/8", json={"footprints": {"banking": True}})
    assert r.status_code == 200

    r = client.post("/user/intake/complete", json={"display_name": "Riley"})
    assert r.status_code == 200

    data = client.get("/user/intake/data").json()
    assert len(data["income_streams"]) == 2
    assert data["bills"][0]["name"] == "Car insurance"
    assert data["collections_items"][0]["creditor"] == "Medical collections"

    summary = client.get("/user/intake/summary").json()
    assert summary["monthly_gross_income"] == 7500
    assert summary["income_breakdown"]["total_monthly"] == 7500
    assert summary["expense_breakdown"]["bills_total"] == 120

