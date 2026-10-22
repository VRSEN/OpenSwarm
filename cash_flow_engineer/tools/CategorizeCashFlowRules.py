import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class CategorizeCashFlowRules(BaseTool):
    """Defines Plaid/API categorization rules for Future/Essentials/Life buckets."""

    merchant_rules: dict[str, str] = Field(default_factory=dict)
    default_bucket: str = Field(default="essentials")

    def run(self) -> str:
        valid = {"future", "essentials", "life"}
        if self.default_bucket.lower() not in valid:
            return json.dumps({"error": "default_bucket must be future, essentials, or life"})

        normalized = {}
        for pattern, bucket in self.merchant_rules.items():
            b = bucket.lower().strip()
            if b not in valid:
                return json.dumps({"error": f"Invalid bucket '{bucket}' for pattern '{pattern}'"})
            normalized[pattern.lower()] = b

        default_rules = {
            "rent|mortgage|utilities|insurance|groceries": "essentials",
            "ira|401k|savings|investment|stability": "future",
            "restaurant|entertainment|shopping|subscription": "life",
        }
        merged = {**default_rules, **normalized}

        return json.dumps(
            {
                "default_bucket": self.default_bucket.lower(),
                "merchant_rules": merged,
                "plaid_integration": "Map transaction merchant_name to rules; unmapped → default_bucket",
                "automation_note": "Remove human emotion from mechanical 15/65/20 execution",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(CategorizeCashFlowRules(merchant_rules={"stripe payout": "future"}).run())
