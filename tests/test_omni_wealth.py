"""OmniWealth engines: risk budget, two-key underwriting, capital waterfall."""

from backend.services.omni_wealth import (
    allocate_capital,
    compare_reinvestment,
    evaluate_move,
    mark_route_done,
    next_tax_deadline,
    route_inflow,
    save_inflow,
    toolbox,
    weekly_review,
)


class _Profile:
    monthly_gross_income = 8000
    monthly_essentials = 5000
    stability_fund_balance = 20000
    stability_fund_target_months = 4
    debts_json = "[]"
    credit_snapshot_json = '{"score_band": "fair", "utilization_pct": 20}'
    wealth_state_json = '{"cash": 5000, "productive_assets": 8000, "productive_assets_known": true, "business_equity_known": true}'
    north_star_json = '{"target_net_worth": 1000000, "target_date": "2027-12-31"}'
    opportunities_json = "[]"
    employment_type = "self_employed"
    business_budget_json = '{"tax_pct": 15}'
    inflows_json = "[]"


class _Starter(_Profile):
    monthly_gross_income = 5000
    monthly_essentials = 2760
    stability_fund_balance = 0


def _by_key(flow):
    return {r["key"]: r for r in flow["routes"]}


def test_inflow_takes_tax_then_bills_first():
    p = _Starter()
    flow = route_inflow(p, 1000, source="Flooring job", date="2026-10-21")
    routes = _by_key(flow)
    assert flow["routes"][0]["key"] == "tax"
    assert routes["tax"]["amount"] == 250  # 25% self-employed floor
    assert routes["essentials"]["amount"] == 750
    assert round(sum(r["amount"] for r in flow["routes"]), 2) == 1000


def test_inflow_after_bills_covered_fills_fund_and_caps_bet():
    p = _Starter()
    save_inflow(p, route_inflow(p, 4000, date="2026-10-02"))
    flow = route_inflow(p, 2000, date="2026-10-21")
    routes = _by_key(flow)
    assert "essentials" not in routes
    assert routes["fund"]["amount"] > routes["life"]["amount"]
    assert routes["bet"]["amount"] <= allocate_capital(p)["risk_budget"]
    assert round(sum(r["amount"] for r in flow["routes"]), 2) == 2000


def test_marking_fund_done_raises_balance():
    p = _Starter()
    save_inflow(p, route_inflow(p, 4000, date="2026-10-02"))
    flow = route_inflow(p, 2000, date="2026-10-21")
    save_inflow(p, flow)
    fund_amt = _by_key(flow)["fund"]["amount"]
    assert mark_route_done(p, flow["inflow_id"], "fund")
    assert p.stability_fund_balance == fund_amt
    assert mark_route_done(p, flow["inflow_id"], "fund") is None


def test_full_fund_routes_to_roth_not_fund():
    p = _Profile()
    save_inflow(p, route_inflow(p, 5000, kind="paycheck", date="2026-10-01"))
    flow = route_inflow(p, 3000, kind="paycheck", date="2026-10-21")
    routes = _by_key(flow)
    assert "tax" not in routes
    assert "fund" not in routes
    assert routes["invest"]["destination"] == "Roth IRA"


def test_toolbox_gates_by_fund():
    starter = {t["id"]: t["status"] for t in toolbox(_Starter())}
    assert starter["hysa"] == "now"
    assert starter["roth_ira"] == "next"
    assert starter["sep_ira"] == "later"
    funded = {t["id"]: t["status"] for t in toolbox(_Profile())}
    assert funded["roth_ira"] == "now" and funded["sep_ira"] == "now"


def test_next_tax_deadline():
    assert next_tax_deadline("2026-10-21")["due"] == "2027-01-15"


def test_funded_user_gets_a_real_risk_budget():
    alloc = allocate_capital(_Profile())
    assert alloc["mode"] == "deploy"
    assert alloc["risk_budget"] > 0
    assert "never" in alloc["rule"].lower()


def test_thin_fund_only_allows_seed_tests():
    p = _Profile()
    p.stability_fund_balance = 500
    alloc = allocate_capital(p)
    assert alloc["mode"] == "seed"
    packet = evaluate_move(
        p,
        {
            "name": "Kalshi longshot",
            "move_type": "kalshi",
            "capital_required": 400,
            "max_loss": 400,
            "expected_profit": 800,
            "exit_plan": "Exit at settlement",
        },
    )
    assert packet["verdict"] in ("TEST", "WAIT", "REJECT")
    assert packet["verdict"] != "BUY"


def test_over_budget_is_rejected():
    packet = evaluate_move(
        _Profile(),
        {
            "name": "All-in crypto",
            "move_type": "crypto",
            "capital_required": 50000,
            "max_loss": 50000,
            "exit_plan": "none really",
        },
    )
    assert packet["verdict"] == "REJECT"
    assert packet["can_commit"] is False


def test_flip_with_exit_can_pass():
    packet = evaluate_move(
        _Profile(),
        {
            "name": "Tool flip",
            "move_type": "flip",
            "capital_required": 400,
            "expected_profit": 200,
            "max_loss": 100,
            "recycle_days": 21,
            "exit_plan": "Sell by day 21 or list at cost",
        },
    )
    assert packet["verdict"] in ("BUY", "TEST")
    assert packet["playbook"]
    assert packet["assurance"]["stability_fund_untouched"] is True


def test_reinvestment_prefers_higher_return():
    result = compare_reinvestment(2000, 40, 10, track_record="proven")
    assert result["winner"] == "internal"


def test_weekly_review_has_actions():
    review = weekly_review(_Profile())
    assert review["this_week"]
    assert review["allocation"]["risk_budget"] >= 0


def test_underwrite_endpoint(client=None):
    from fastapi.testclient import TestClient
    from backend.app import create_mechanical_app

    app = create_mechanical_app()
    with TestClient(app) as c:
        c.post("/user/intake/step/1", json={"display_name": "Alex", "primary_trade": "HVAC"})
        c.post(
            "/user/intake/step/2",
            json={"monthly_gross_income": 8000, "monthly_essentials": 5000, "stability_fund_balance": 18000},
        )
        c.post("/user/intake/complete", json={"display_name": "Alex"})
        cmd = c.get("/wealth/command")
        assert cmd.status_code == 200
        assert "risk_budget" in cmd.json()["allocation"]
        r = c.post(
            "/wealth/moves/underwrite",
            json={
                "name": "Kalshi weather",
                "move_type": "kalshi",
                "capital_required": 100,
                "expected_profit": 40,
                "max_loss": 100,
                "recycle_days": 7,
                "exit_plan": "Hold to settlement",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] in ("BUY", "TEST", "WAIT", "REJECT", "ESCALATE")
        assert "playbook" in body
