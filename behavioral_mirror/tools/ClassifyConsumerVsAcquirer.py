import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ClassifyConsumerVsAcquirer(BaseTool):
    """Tag spend as consumer (ego/status) or acquirer (future control/asset) for Quiet Builder score."""

    amount: float = Field(..., gt=0)
    category: str = Field(...)
    bucket: str = Field(default="life")
    linked_to_asset: bool = Field(default=False)
    emotional_trigger: str = Field(default="unknown")

    def run(self) -> str:
        trigger = self.emotional_trigger.lower()
        ego_triggers = {"status", "social", "boredom"}
        is_consumer = (
            self.bucket.lower() == "life"
            and not self.linked_to_asset
            and (trigger in ego_triggers or not self.linked_to_asset)
        )
        tag = "consumer" if is_consumer else "acquirer"
        return json.dumps(
            {
                "amount": self.amount,
                "category": self.category,
                "tag": tag,
                "quiet_builder_impact": "penalty" if is_consumer else "bonus",
                "mirror_note": (
                    f"${self.amount:.2f} classified as {tag} spend—"
                    f"{'feeds lifestyle inflation' if is_consumer else 'feeds future control'}."
                ),
            },
            indent=2,
        )


if __name__ == "__main__":
    print(ClassifyConsumerVsAcquirer(amount=200, category="luxury watch", emotional_trigger="status").run())
