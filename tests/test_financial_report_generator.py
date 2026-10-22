"""Generate financial report files to mnt."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.user_profile import UserProfile
from backend.services.financial_report_generator import generate_financial_report


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    profile = UserProfile(
        user_id="test-user",
        display_name="Test Architect",
        primary_trade="Consulting",
        monthly_gross_income=6000,
        monthly_essentials=3500,
        stability_fund_balance=7000,
        stability_fund_target_months=4,
        debts_json='[{"name": "Card", "balance": 2000, "apr": 18, "minimum_payment": 50}]',
        credit_snapshot_json='{"score_band": "good", "utilization_pct": 25}',
        business_budget_json='{"profit_pct": 5, "tax_pct": 15, "owner_pay_pct": 50, "opex_pct": 30}',
        cashflow_quadrant_primary="S",
        cashflow_quadrant_json='{"E": 0, "S": 100, "B": 0, "I": 0}',
        intake_step=7,
        onboarding_completed=True,
    )
    session.add(profile)
    session.commit()
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    monkeypatch.setattr(
        "backend.services.financial_report_generator._mnt_documents_dir",
        lambda user_id: mnt / f"architect_reports_{user_id.replace('-', '_')}" / "documents",
    )
    yield profile
    session.close()


def test_generate_markdown_and_html(db):
    result = generate_financial_report(db, template_id="financial_snapshot", formats=["markdown", "html"])
    assert result["template_id"] == "financial_snapshot"
    formats = {f["format"] for f in result["files"]}
    assert "markdown" in formats
    assert "html" in formats


def test_generate_pdf_optional(db):
    result = generate_financial_report(
        db, template_id="financial_snapshot", formats=["pdf", "html", "markdown"]
    )
    formats = {f["format"] for f in result["files"]}
    assert "html" in formats
    assert "markdown" in formats
    # PDF only when WeasyPrint system libs are installed
    if "pdf" in formats:
        assert any(f["format"] == "pdf" for f in result["files"])
