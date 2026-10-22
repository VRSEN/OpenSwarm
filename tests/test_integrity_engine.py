import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/test_integrity.db"

from backend.app import create_mechanical_app
from backend.services.reputation_engine import (
    SelfTrustEvent,
    check_fund_now_gate,
    compute_full_reputation,
    compute_self_trust_index,
)
from backend.services.spread_engine import apply_reputation_coc_adjustment, evaluate_fund_eligibility


@pytest.fixture
def client():
    app = create_mechanical_app()
    with TestClient(app) as c:
        yield c


def test_self_trust_index():
    events = [
        SelfTrustEvent(kept_commitment=True),
        SelfTrustEvent(kept_commitment=True),
        SelfTrustEvent(kept_commitment=False, event_type="pause_broken"),
    ]
    result = compute_self_trust_index(events)
    assert 0 <= result["self_trust_index"] <= 100
    assert result["pause_breaches"] == 1


def test_self_trust_floor_blocks_fund():
    gate = check_fund_now_gate(composite_score=80, self_trust_pillar=55)
    assert gate["eligible"] is False
    assert "Self-Trust" in gate["block_reason"]


def test_gold_coc_adjustment():
    adjusted = apply_reputation_coc_adjustment(6.0, "Gold")
    assert adjusted == pytest.approx(5.5)


def test_fund_eligibility_platinum():
    result = evaluate_fund_eligibility(92, 85, "Platinum", 1000)
    assert result["approved"] is True
    assert result["pipeline_priority"] is True


def test_full_reputation_composite():
    rep = compute_full_reputation(
        self_trust_events=[SelfTrustEvent(kept_commitment=True) for _ in range(5)],
    )
    assert "pillars" in rep
    assert rep["tier"] in ("Bronze", "Silver", "Gold", "Platinum")


def test_reputation_score_endpoint(client):
    r = client.get("/reputation/score")
    assert r.status_code == 200
    data = r.json()
    assert "reputation_credit_score" in data
    assert len(data["pillars"]) == 5


def test_character_mirror_endpoint(client):
    r = client.get("/dashboard/mirror?essentials_pct=70&pause_breaches_recent=1")
    assert r.status_code == 200
    data = r.json()
    assert "silent_kpis" in data
    assert "character_mirror" in data


def test_portable_export(client):
    r = client.get("/reputation/portable")
    assert r.status_code == 200
    assert "summary" in r.json()


def test_vet_provider(client):
    r = client.post(
        "/reputation/vet-provider",
        json={
            "provider_name": "TestCo",
            "engagements": [{"delivered": True, "on_time": True}],
            "references_verified": 1,
            "project_value": 500,
        },
    )
    assert r.status_code == 200
    assert r.json()["verdict"] in ("hire", "monitor", "avoid")
