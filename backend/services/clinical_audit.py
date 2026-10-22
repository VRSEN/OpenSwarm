"""Generate Clinical Life Audit from authorized digital footprints (Plaid/calendar/screen time)."""

from __future__ import annotations

from typing import Any


def generate_clinical_audit(
    *,
    banking_connected: bool,
    calendar_connected: bool,
    screen_connected: bool,
    profile=None,
) -> dict[str, Any]:
    """
    Day Zero audit from footprints. Uses profile intake numbers when data_source=manual.
    Demo synthesis only for demo mode or when no intake exists.
    """
    if not any([banking_connected, calendar_connected, screen_connected]):
        return {
            "ready": False,
            "message": "Connect at least one footprint to generate behavioral mirror patterns.",
        }

    if profile and getattr(profile, "data_source", None) == "manual" and profile.monthly_gross_income > 0:
        return _audit_from_profile(
            profile,
            banking_connected=banking_connected,
            calendar_connected=calendar_connected,
            screen_connected=screen_connected,
        )

    return _synthesize_from_footprints(
        banking_connected=banking_connected,
        calendar_connected=calendar_connected,
        screen_connected=screen_connected,
        data_source="demo",
    )


def _audit_from_profile(
    profile,
    *,
    banking_connected: bool,
    calendar_connected: bool,
    screen_connected: bool,
) -> dict[str, Any]:
    inflow = profile.monthly_gross_income
    essentials = profile.monthly_essentials
    life_est = max(inflow * 0.20, 0)
    future_est = max(inflow * 0.15, 0)
    essentials_pct = round(essentials / inflow * 100, 1) if inflow else 0
    life_pct = round(life_est / inflow * 100, 1) if inflow else 0
    future_pct = round(future_est / inflow * 100, 1) if inflow else 0

    patterns = []
    if essentials_pct > 65:
        patterns.append(
            {
                "id": "essentials_over",
                "mirror": f"Essentials at {essentials_pct}% of income—target is 65%. Structural fragility.",
                "type": "structure",
                "severity": "red",
                "choice_prompt": "Will you cap Essentials before chasing opportunities?",
            }
        )
    if profile.stability_fund_balance < essentials * 3:
        patterns.append(
            {
                "id": "fund_gap",
                "mirror": "Stability Fund below 3 months of Essentials—retention before leverage.",
                "type": "structure",
                "severity": "amber",
                "choice_prompt": "Will you route Future bucket dollars here first?",
            }
        )

    if calendar_connected:
        patterns.append(
            {
                "id": "creation_gap",
                "mirror": "Calendar connected—defend one Creation Hour daily for skill stacking.",
                "type": "creation",
                "severity": "amber",
                "choice_prompt": "Will you block deep work on your calendar?",
            }
        )

    return {
        "ready": True,
        "day_zero": False,
        "data_source": "manual",
        "audit_label": "Behavioral Mirror (your numbers)",
        "summary": "Patterns below use your intake numbers—not demo banking data.",
        "financial_mirror": {
            "monthly_inflow": inflow,
            "essentials_actual_pct": essentials_pct,
            "life_actual_pct": life_pct,
            "future_actual_pct": future_pct,
            "target_split": {"future": 15, "essentials": 65, "life": 20},
            "stability_fund_estimate": profile.stability_fund_balance,
            "stability_fund_target": essentials * profile.stability_fund_target_months,
        },
        "time_mirror": {
            "consumption_vs_creation_pct": {"consumption": 55, "creation": 45},
            "creation_hours_week": 5.5 if calendar_connected else None,
        },
        "patterns": patterns or [
            {
                "id": "on_track",
                "mirror": "Your intake numbers fit the 15/65/20 structure—focus on consistency.",
                "type": "structure",
                "severity": "green",
                "choice_prompt": "Will you honor Fork Moments on Life spending?",
            }
        ],
        "sources_connected": {
            "banking": banking_connected,
            "calendar": calendar_connected,
            "screen_time": screen_connected,
        },
    }


def _synthesize_from_footprints(
    banking_connected: bool,
    calendar_connected: bool,
    screen_connected: bool,
    data_source: str = "demo",
) -> dict[str, Any]:
    monthly_inflow = 7200.0 if banking_connected else 0.0
    essentials = round(monthly_inflow * 0.68, 2) if banking_connected else 0.0
    life_spend = round(monthly_inflow * 0.24, 2) if banking_connected else 0.0
    future_saved = round(monthly_inflow * 0.08, 2) if banking_connected else 0.0

    patterns = []
    if banking_connected:
        patterns.extend(
            [
                {
                    "id": "life_drift",
                    "mirror": "Life bucket at 24% of inflow—target is 20%. $288/mo above structural plan.",
                    "type": "consumption",
                    "severity": "amber",
                    "choice_prompt": "Do you recognize this leak?",
                },
                {
                    "id": "status_cluster",
                    "mirror": "3 similar discretionary charges in 5 days—status/social pattern detected.",
                    "type": "consumption",
                    "severity": "red",
                    "choice_prompt": "Is this comfort spending, not creation?",
                },
                {
                    "id": "future_underfund",
                    "mirror": "Only 8% routed to Future bucket—target 15%. Stability Fund cannot fill at this rate.",
                    "type": "structure",
                    "severity": "amber",
                    "choice_prompt": "Will you protect the Future bucket on the next inflow?",
                },
            ]
        )
    if calendar_connected:
        patterns.append(
            {
                "id": "creation_gap",
                "mirror": "Calendar shows 41% of work hours in admin/reactive tasks—11% in deep creation blocks.",
                "type": "creation",
                "severity": "amber",
                "choice_prompt": "Will you defend one Creation Hour daily?",
            }
        )
    if screen_connected:
        patterns.append(
            {
                "id": "screen_drift",
                "mirror": "2.4 hrs/day average on consumption apps during work blocks—attention leak.",
                "type": "consumption",
                "severity": "amber",
                "choice_prompt": "Do you accept this as changeable, not permanent?",
            }
        )

    consumption_pct = 62
    creation_pct = 38
    if calendar_connected:
        creation_pct = 28
        consumption_pct = 72

    return {
        "ready": True,
        "day_zero": True,
        "data_source": data_source,
        "audit_label": "Clinical Life Audit (demo)",
        "summary": (
            "Your authorized footprints show where hours and dollars leak. "
            "This is observation—not judgment. You choose what to change."
        ),
        "financial_mirror": {
            "monthly_inflow": monthly_inflow,
            "essentials_actual_pct": round(essentials / monthly_inflow * 100, 1) if monthly_inflow else 0,
            "life_actual_pct": round(life_spend / monthly_inflow * 100, 1) if monthly_inflow else 0,
            "future_actual_pct": round(future_saved / monthly_inflow * 100, 1) if monthly_inflow else 0,
            "target_split": {"future": 15, "essentials": 65, "life": 20},
            "stability_fund_estimate": round(essentials * 2.1, 2) if banking_connected else 0,
            "stability_fund_target": round(essentials * 4, 2) if banking_connected else 0,
        },
        "time_mirror": {
            "consumption_vs_creation_pct": {
                "consumption": consumption_pct,
                "creation": creation_pct,
            },
            "creation_hours_week": 5.5 if calendar_connected else None,
        },
        "patterns": patterns,
        "sources_connected": {
            "banking": banking_connected,
            "calendar": calendar_connected,
            "screen_time": screen_connected,
        },
    }


def derive_profile_from_audit(audit: dict, display_name: str = "Architect") -> dict[str, float | str | bool]:
    """Map audit outputs to profile fields—no manual data entry."""
    fin = audit.get("financial_mirror", {})
    inflow = fin.get("monthly_inflow", 0)
    essentials_pct = fin.get("essentials_actual_pct", 65) / 100
    return {
        "display_name": display_name,
        "monthly_gross_income": inflow,
        "monthly_essentials": round(inflow * essentials_pct, 2) if inflow else 0,
        "stability_fund_balance": fin.get("stability_fund_estimate", 0),
        "stability_fund_target_months": 4,
        "focus_season_active": True,
    }
