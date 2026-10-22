import pytest
from fastapi.testclient import TestClient

from backend.app import create_mechanical_app


@pytest.fixture
def client():
    app = create_mechanical_app()
    with TestClient(app) as c:
        yield c


def test_intake_status_new_user(client):
    client.post("/user/intake/reset?user_id=test_fresh")
    r = client.get("/user/intake/status?user_id=test_fresh")
    assert r.status_code == 200
    assert r.json()["intake_completed"] is False


def test_full_intake_replaces_demo_flow(client):
    client.post("/user/intake/step/1", json={"display_name": "Jordan", "primary_trade": "Design"})
    client.post(
        "/user/intake/step/2",
        json={"monthly_gross_income": 5000, "monthly_essentials": 3200, "stability_fund_balance": 1000},
    )
    client.post("/user/intake/step/3", json={"debts": []})
    client.post("/user/intake/step/4", json={"score_band": "good", "utilization_pct": 20})
    client.post(
        "/user/intake/step/5",
        json={"monthly_revenue": 5000, "profit_pct": 5, "tax_pct": 15, "owner_pay_pct": 50, "opex_pct": 30},
    )
    sign = client.post("/user/intake/complete", json={"display_name": "Jordan"})
    assert sign.status_code == 200
    assert sign.json()["intake_completed"] is True

    profile = client.get("/user/profile").json()
    assert profile["intake_completed"] is True
    assert profile["data_source"] == "manual"

    journey = client.get("/user/journey").json()
    assert journey["onboarding_required"] is False

    pause = client.post(
        "/mirror/fork-moments/pause",
        json={"item_description": "Headphones", "amount": 199, "bucket": "life"},
    )
    assert pause.status_code == 200
    assert pause.json()["status"] == "paused"
    pause_id = pause.json()["pause_id"]
    ack = client.post(
        "/mirror/fork-moments/acknowledge",
        json={"pause_id": pause_id, "emotion": "stress", "choose_architect_path": True},
    )
    assert ack.status_code == 200
    gone = client.post("/mirror/fork-moments/release", json={"pause_id": pause_id})
    assert gone.status_code == 200
    assert gone.json()["released"] == 1


def test_clinical_audit_optional_footprints(client):
    client.post("/user/intake/step/1", json={"display_name": "Sam", "primary_trade": "Dev"})
    client.post(
        "/user/intake/step/2",
        json={"monthly_gross_income": 6000, "monthly_essentials": 3900, "stability_fund_balance": 500},
    )
    client.post("/user/intake/step/3", json={"debts": []})
    client.post("/user/intake/step/4", json={"score_band": "unknown"})
    client.post(
        "/user/intake/step/5",
        json={"monthly_revenue": 6000, "profit_pct": 5, "tax_pct": 15, "owner_pay_pct": 50, "opex_pct": 30},
    )
    client.post("/user/intake/step/6", json={"footprints": {"banking": True, "calendar": False, "screen_time": False}})
    client.post("/user/intake/complete", json={})

    audit = client.get("/user/clinical-audit").json()
    assert audit["ready"] is True
    assert audit.get("data_source") in ("manual", None) or audit["financial_mirror"]["monthly_inflow"] == 6000
