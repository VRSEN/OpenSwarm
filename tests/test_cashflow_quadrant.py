"""Cashflow Quadrant (ESBI) assessment."""

from types import SimpleNamespace

from backend.services.cashflow_quadrant import (
    assess_cashflow_quadrant,
    assess_from_profile,
    default_income_mix,
    infer_primary_quadrant,
)


def test_infer_primary_from_employment():
    assert infer_primary_quadrant("self_employed") == "S"
    assert infer_primary_quadrant("business_owner") == "B"
    assert infer_primary_quadrant("side_hustle") == "S"
    assert infer_primary_quadrant("employee") == "E"


def test_side_hustle_default_mix():
    mix = default_income_mix("S", "side_hustle")
    assert mix["E"] == 60
    assert mix["S"] == 40


def test_assess_badge_and_target():
    result = assess_cashflow_quadrant(
        primary_quadrant="S",
        employment_type="self_employed",
        wealth_stage="Stability",
        income_mix={"E": 0, "S": 100, "B": 0, "I": 0},
    )
    assert result["badge"] == "S → B"
    assert result["target_quadrant"] == "B"
    assert result["left_side_pct"] == 100.0
    assert "disclaimer" in result


def test_assess_from_profile():
    profile = SimpleNamespace(
        cashflow_quadrant_primary="S",
        cashflow_quadrant_json='{"E": 0, "S": 100, "B": 0, "I": 0}',
        employment_type="self_employed",
    )
    result = assess_from_profile(profile, "Asset Acquisition")
    assert result["target_quadrant"] == "I"
    assert result["badge"] == "S → I"
