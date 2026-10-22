"""Tests for architect memory service."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.user_profile import UserProfile
import backend.repositories.memory_repo as memory_repo
from backend.services.memory_service import (
    add_memory_fact,
    build_architect_dossier,
    format_dossier_for_instructions,
    get_chat_history,
    merge_chat_history,
    record_improvement_snapshot,
    save_chat_history,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    profile = UserProfile(
        user_id="test-user",
        display_name="Test Architect",
        monthly_gross_income=5000,
        monthly_essentials=3000,
        stability_fund_balance=6000,
        cashflow_quadrant_primary="S",
        cashflow_quadrant_json='{"E": 0, "S": 100, "B": 0, "I": 0}',
        intake_step=7,
    )
    session.add(profile)
    session.commit()
    yield session
    session.close()


def test_build_dossier_includes_identity(db):
    dossier = build_architect_dossier(db, "test-user")
    assert dossier["architect_identity"]["display_name"] == "Test Architect"
    assert dossier["user_id"] == "test-user"
    assert "journey" in dossier
    assert "financial_summary" in dossier
    assert dossier.get("cashflow_quadrant")
    assert dossier["cashflow_quadrant"]["primary_quadrant"] == "S"


def test_format_dossier_includes_esbi(db):
    dossier = build_architect_dossier(db, "test-user")
    text = format_dossier_for_instructions(dossier)
    assert "Cashflow Quadrant (ESBI)" in text
    assert "S → B" in text or "primary" in text.lower()
    assert "NOT Covey Quadrant II" in text


def test_chat_persistence(db):
    msgs = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]
    save_chat_history(db, "test-user", msgs)
    loaded = get_chat_history(db, "test-user")
    assert len(loaded) == 2
    assert loaded[0]["content"] == "Hello"


def test_merge_chat_history(db):
    prior = [{"role": "user", "content": "First"}]
    new = [{"role": "assistant", "content": "Reply"}]
    merged = merge_chat_history(prior, new)
    assert len(merged) == 2


def test_memory_fact(db):
    fact = add_memory_fact(db, "test-user", "User is in Georgia", category="tax")
    assert fact.category == "tax"
    facts = memory_repo.list_facts(db, "test-user")
    assert len(facts) == 1


def test_improvement_snapshot(db):
    snap = record_improvement_snapshot(db, "test-user", note="Test snapshot")
    assert snap is not None
    assert snap.stage
    metrics = json.loads(snap.metrics_json)
    assert "monthly_gross_income" in metrics
