"""Fork Moments — friction-based pause and emotional acknowledgment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

EMOTION_OPTIONS = ("stress", "boredom", "status", "social", "comfort", "unknown")

IDENTITY_FRAMES = {
    "stress": "You are an architect who pauses under pressure—not a reactor.",
    "boredom": "You are an architect who builds systems—not one who fills silence with spend.",
    "status": "You are an architect who invests in assets—not performances.",
    "social": "You are an architect who chooses direction—not approval.",
    "comfort": "You are an architect who protects their future—not their mood.",
    "unknown": "You are an architect who protects their future.",
}


def create_fork_pause(
    item_description: str,
    amount: float,
    bucket: str = "life",
) -> dict[str, Any]:
    if bucket.lower() in ("essentials", "future"):
        return {
            "status": "exempt",
            "message": "Essentials and Future purchases bypass the 72-hour Fork Moment.",
        }

    now = datetime.now(timezone.utc)
    unlock = now + timedelta(hours=72)
    return {
        "status": "paused",
        "fork_moment": True,
        "item_description": item_description,
        "amount": amount,
        "bucket": bucket,
        "pause_started_at": now.isoformat(),
        "unlock_at": unlock.isoformat(),
        "requires_emotion_ack": True,
        "message": "Fork Moment: acknowledge what drives this spend before the 72-hour clock completes.",
    }


def acknowledge_emotion(emotion: str, accepted_architect_path: bool) -> dict[str, Any]:
    emotion = emotion.lower() if emotion in EMOTION_OPTIONS else "unknown"
    if not accepted_architect_path:
        return {
            "acknowledged": True,
            "emotion": emotion,
            "identity_notification": "You chose awareness. The pause remains—return in 72 hours or release.",
            "action": "pause_continues",
        }
    return {
        "acknowledged": True,
        "emotion": emotion,
        "identity_notification": IDENTITY_FRAMES.get(emotion, IDENTITY_FRAMES["unknown"]),
        "action": "pause_logged",
    }


def dollar_missions(monthly_inflow: float) -> dict[str, Any]:
    if monthly_inflow <= 0:
        return {"missions": [], "gap_message": "Complete intake with your income to assign dollar missions."}

    future = round(monthly_inflow * 0.15, 2)
    essentials = round(monthly_inflow * 0.65, 2)
    life = round(monthly_inflow * 0.20, 2)
    surplus = round(monthly_inflow - essentials - life - future, 2)

    return {
        "missions": [
            {"job": "Stability Fund", "bucket": "future", "amount": future, "rule": "15% of every inflow"},
            {"job": "Essentials machine", "bucket": "essentials", "amount": essentials, "rule": "65% cap—non-negotiable"},
            {"job": "Life (with pause)", "bucket": "life", "amount": life, "rule": "20%—Fork Moments apply"},
        ],
        "income_expense_gap": surplus,
        "gap_message": (
            f"${abs(surplus):,.0f} {'surplus' if surplus >= 0 else 'shortfall'} after 15/65/20—"
            + ("expand Future bucket." if surplus >= 0 else "reduce Life or raise income density.")
        ),
        "steering_prompt": "Review missions—not re-enter numbers. Adjust direction, not spreadsheets.",
    }
