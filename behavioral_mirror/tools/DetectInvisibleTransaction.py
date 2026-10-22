import json

from agency_swarm.tools import BaseTool
from pydantic import Field

INVISIBLE_TRIGGERS = {"stress", "boredom", "status", "social", "unknown"}


class DetectInvisibleTransaction(BaseTool):
    """Flags transactions that bypass the 15/65/20 plan (invisible/emotion-triggered)."""

    transaction_amount: float = Field(..., gt=0)
    transaction_category: str = Field(...)
    stated_budget_bucket: str = Field(default="unassigned")
    emotional_trigger: str = Field(default="unknown")
    time_of_day: str = Field(default="")
    days_since_last_similar: int = Field(default=0, ge=0)

    def run(self) -> str:
        bucket = self.stated_budget_bucket.lower().strip()
        trigger = self.emotional_trigger.lower().strip()

        is_invisible = bucket in ("unassigned", "life") and (
            trigger in INVISIBLE_TRIGGERS
            or self.days_since_last_similar <= 3
            or bucket == "unassigned"
        )

        pattern_note = ""
        if self.days_since_last_similar <= 3:
            pattern_note = f"Similar transaction {self.days_since_last_similar} days ago—pattern detected."
        if trigger != "unknown":
            pattern_note += f" Trigger signal: {trigger}."

        result = {
            "transaction_amount": self.transaction_amount,
            "category": self.transaction_category,
            "bucket": bucket,
            "visibility": "invisible" if is_invisible else "visible",
            "emotional_trigger": trigger,
            "mirror_reflection": (
                f"${self.transaction_amount:.2f} in '{self.transaction_category}' "
                f"classified as {'invisible' if is_invisible else 'visible'} to your plan. {pattern_note}".strip()
            ),
            "recommended_action": "Enforce72HourPauseRule" if is_invisible and bucket == "life" else "LogBehaviorPattern",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = DetectInvisibleTransaction(
        transaction_amount=189,
        transaction_category="online shopping",
        stated_budget_bucket="life",
        emotional_trigger="boredom",
        days_since_last_similar=1,
    )
    print(tool.run())
