"""Rich Dad Cashflow Quadrant (ESBI) — assessment for self-employed operators."""

from __future__ import annotations

import json
from typing import Any

QUADRANTS = ("E", "S", "B", "I")

QUADRANT_LABELS = {
    "E": "Employee",
    "S": "Self-employed",
    "B": "Business owner",
    "I": "Investor",
}

QUADRANT_SIDE = {
    "E": "left",
    "S": "left",
    "B": "right",
    "I": "right",
}

QUADRANT_DESCRIPTIONS = {
    "E": "Trades time for a paycheck; values security and benefits.",
    "S": "Owns a job — if you stop working, income stops.",
    "B": "Owns a system — business can run without daily presence.",
    "I": "Money works through assets — cash flow from capital.",
}

STAGE_TARGET_QUADRANT = {
    "Stability": "B",
    "Skill Stacking": "B",
    "Asset Acquisition": "I",
    "System Scaling": "I",
    "Sovereignty": "I",
}

STAGE_TRANSITION_HINT = {
    "Stability": "Secure the S-quadrant base (Stability Fund + 15/65/20), then productize one offer.",
    "Skill Stacking": "Raise $/hour and package a fixed-scope product — first step from S toward B.",
    "Asset Acquisition": "Build or buy spread-positive assets; allocate Future bucket to I-path investments.",
    "System Scaling": "Recycle capital; delegate or automate delivery where possible.",
    "Sovereignty": "Maintain passive cash flow and document legacy (Step-Up Basis planning).",
}


def infer_primary_quadrant(employment_type: str | None) -> str:
    mapping = {
        "self_employed": "S",
        "business_owner": "B",
        "side_hustle": "S",
        "employee": "E",
    }
    return mapping.get(employment_type or "", "S")


def parse_income_mix(raw: str | dict | None) -> dict[str, float]:
    if not raw:
        return {"E": 0, "S": 0, "B": 0, "I": 0}
    if isinstance(raw, str):
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            data = {}
    else:
        data = raw
    return {
        "E": float(data.get("E", data.get("e_pct", 0)) or 0),
        "S": float(data.get("S", data.get("s_pct", 0)) or 0),
        "B": float(data.get("B", data.get("b_pct", 0)) or 0),
        "I": float(data.get("I", data.get("i_pct", 0)) or 0),
    }


def default_income_mix(primary: str, employment_type: str | None) -> dict[str, float]:
    mix = {"E": 0.0, "S": 0.0, "B": 0.0, "I": 0.0}
    if employment_type == "side_hustle":
        mix["E"] = 60.0
        mix["S"] = 40.0
        return mix
    if primary in mix:
        mix[primary] = 100.0
    else:
        mix["S"] = 100.0
    return mix


def assess_cashflow_quadrant(
    *,
    primary_quadrant: str | None,
    employment_type: str | None,
    wealth_stage: str,
    income_mix: dict[str, float] | None = None,
) -> dict[str, Any]:
    primary = (primary_quadrant or "").upper()
    if primary not in QUADRANTS:
        primary = infer_primary_quadrant(employment_type)

    mix = income_mix or default_income_mix(primary, employment_type)
    mix_total = sum(mix.values())
    if mix_total <= 0:
        mix = default_income_mix(primary, employment_type)
        mix_total = 100.0
    elif abs(mix_total - 100) > 1:
        mix = {k: round(v / mix_total * 100, 1) for k, v in mix.items()}

    target = STAGE_TARGET_QUADRANT.get(wealth_stage, "B")
    left_pct = round(mix.get("E", 0) + mix.get("S", 0), 1)
    right_pct = round(mix.get("B", 0) + mix.get("I", 0), 1)

    transition = _transition_label(primary, target)
    next_move = STAGE_TRANSITION_HINT.get(wealth_stage, STAGE_TRANSITION_HINT["Stability"])

    return {
        "primary_quadrant": primary,
        "primary_label": QUADRANT_LABELS[primary],
        "primary_side": QUADRANT_SIDE[primary],
        "primary_description": QUADRANT_DESCRIPTIONS[primary],
        "target_quadrant": target,
        "target_label": QUADRANT_LABELS[target],
        "transition": transition,
        "badge": f"{primary} → {target}",
        "income_mix_pct": mix,
        "left_side_pct": left_pct,
        "right_side_pct": right_pct,
        "on_left_side": left_pct >= right_pct,
        "next_mechanical_move": next_move,
        "disclaimer": (
            "Educational ESBI framework inspired by cashflow quadrant concepts — "
            "not affiliated with Rich Dad Company."
        ),
    }


def _transition_label(current: str, target: str) -> str:
    if current == target:
        return f"Deepen {QUADRANT_LABELS[current]} skills and cash-flow systems."
    order = list(QUADRANTS)
    if order.index(current) < order.index(target):
        return f"Move from {QUADRANT_LABELS[current]} toward {QUADRANT_LABELS[target]}."
    return f"Strengthen {QUADRANT_LABELS[target]} while honoring income from {QUADRANT_LABELS[current]}."


def assess_from_profile(profile, wealth_stage: str) -> dict[str, Any]:
    primary = getattr(profile, "cashflow_quadrant_primary", None) or infer_primary_quadrant(
        profile.employment_type
    )
    mix = parse_income_mix(getattr(profile, "cashflow_quadrant_json", None))
    if sum(mix.values()) <= 0:
        mix = default_income_mix(primary, profile.employment_type)
    return assess_cashflow_quadrant(
        primary_quadrant=primary,
        employment_type=profile.employment_type,
        wealth_stage=wealth_stage,
        income_mix=mix,
    )
