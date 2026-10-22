"""Pitch card file generation."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.user_profile import UserProfile
from backend.services.pitch_card_generator import generate_pitch_card


@pytest.fixture()
def profile(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    row = UserProfile(
        user_id="test-user",
        display_name="Test Architect",
        primary_trade="Consulting",
        monthly_gross_income=6000,
        monthly_essentials=3500,
        stability_fund_balance=7000,
        cashflow_quadrant_primary="S",
        cashflow_quadrant_json='{"E": 0, "S": 100, "B": 0, "I": 0}',
        onboarding_completed=True,
    )
    session.add(row)
    session.commit()
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    monkeypatch.setattr(
        "backend.services.pitch_card_generator._mnt_presentations_dir",
        lambda user_id: mnt / f"architect_pitchcards_{user_id.replace('-', '_')}" / "presentations",
    )
    yield row
    session.close()


def test_generate_pitch_card_html(profile):
    result = generate_pitch_card(profile, template_id="operator_intro", formats=["html"])
    assert result["template_id"] == "operator_intro"
    assert any(f["format"] == "html" for f in result["files"])
    assert result["preview"]["preview_type"] == "pitch_card"
