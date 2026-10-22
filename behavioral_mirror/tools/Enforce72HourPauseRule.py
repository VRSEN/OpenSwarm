import json
from datetime import datetime, timedelta, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field


class Enforce72HourPauseRule(BaseTool):
    """Creates a mandatory 72-hour hold on non-essential purchases."""

    item_description: str = Field(...)
    amount: float = Field(..., gt=0)
    bucket: str = Field(default="life")
    is_essential: bool = Field(default=False)

    def run(self) -> str:
        if self.is_essential or self.bucket.lower() in ("essentials", "future"):
            return json.dumps(
                {
                    "verdict": "exempt",
                    "reason": "Essentials and Future bucket items bypass 72-hour pause.",
                    "amount": self.amount,
                    "item": self.item_description,
                },
                indent=2,
            )

        now = datetime.now(timezone.utc)
        unlock_at = now + timedelta(hours=72)

        result = {
            "verdict": "paused",
            "item": self.item_description,
            "amount": self.amount,
            "bucket": self.bucket,
            "pause_started_at": now.isoformat(),
            "unlock_at": unlock_at.isoformat(),
            "hours_remaining": 72,
            "rule": "Non-essential Life-bucket purchases require 72-hour intentional delay.",
            "identity_reminder": "You are an architect who protects their future—not a reactor to impulse.",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    print(Enforce72HourPauseRule(item_description="New headphones", amount=249, bucket="life").run())
