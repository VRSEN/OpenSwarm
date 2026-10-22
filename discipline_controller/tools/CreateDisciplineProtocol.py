import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class CreateDisciplineProtocol(BaseTool):
    """
    Generates a personalized weekly or monthly mechanical checklist
    aligned to Profit First and the user's financial stage.
    """

    financial_stage: str = Field(..., description="Survival, Stability, Growth, or Sovereignty.")
    bank_account_labels: list[str] = Field(
        ...,
        min_length=1,
        description="User-defined account names for buckets (e.g., Profit, Tax, Owner Pay, OpEx).",
    )
    review_frequency: str = Field(default="weekly", description="weekly, biweekly, or monthly.")

    def run(self) -> str:
        freq = self.review_frequency.lower().strip()
        if freq not in ("weekly", "biweekly", "monthly"):
            return json.dumps({"error": "review_frequency must be weekly, biweekly, or monthly."})

        base_tasks = [
            "On every deposit: run Profit First split before any spending.",
            f"Review runway and bucket balances ({freq}).",
            "Log all business expenses to OpEx category same day.",
        ]

        stage_tasks = {
            "Survival": [
                "Deny non-essential recurring charges.",
                "Transfer Tax bucket funds—do not borrow from OpEx for taxes.",
                "Track days of runway; alert if < 90 days.",
            ],
            "Stability": [
                "Increase tax reserve by at least 10% of monthly target.",
                "Audit subscriptions for cancellation candidates.",
                "Build emergency fund transfer from Profit bucket.",
            ],
            "Growth": [
                "Confirm tax reserve ≥ 90% of annual target.",
                "Contribute to retirement account per Wealth Architect plan.",
                "Review arbitrage pipeline for A-tier opportunities only.",
            ],
            "Sovereignty": [
                "Rebalance portfolio per Investment Policy Statement.",
                "Deploy arbitrage capital ≤ 25% of liquid assets.",
                "Quarterly sovereignty number progress review.",
            ],
        }

        accounts_note = f"Bucket accounts: {', '.join(self.bank_account_labels)}"
        schedule = {
            "frequency": freq,
            "tasks": base_tasks + stage_tasks.get(self.financial_stage, []),
            "accounts": accounts_note,
            "financial_stage": self.financial_stage,
        }

        return json.dumps(schedule, indent=2)


if __name__ == "__main__":
    tool = CreateDisciplineProtocol(
        financial_stage="Stability",
        bank_account_labels=["Profit", "Tax Reserve", "Owner Pay", "OpEx"],
        review_frequency="weekly",
    )
    print(tool.run())
