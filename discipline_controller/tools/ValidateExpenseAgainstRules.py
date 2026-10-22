import json

from agency_swarm.tools import BaseTool
from pydantic import Field

ESSENTIAL_CATEGORIES = {"rent", "utilities", "insurance", "food", "healthcare", "tax", "debt_minimum"}


class ValidateExpenseAgainstRules(BaseTool):
    """
    Checks a proposed expense against stage-based spending rules and OpEx bucket availability.
    """

    expense_amount: float = Field(..., gt=0, description="Proposed expense amount.")
    expense_category: str = Field(..., description="Category: opex, owner_pay, profit, tax, investment, or descriptive name.")
    available_opex_balance: float = Field(..., ge=0, description="Current OpEx bucket balance.")
    financial_stage: str = Field(..., description="Survival, Stability, Growth, or Sovereignty.")
    is_recurring: bool = Field(default=False, description="True if this is a recurring subscription or payment.")
    expense_description: str = Field(default="", description="Brief description of the expense.")

    def run(self) -> str:
        category_lower = self.expense_category.lower().strip()
        stage = self.financial_stage.strip()

        if stage == "Survival":
            if self.is_recurring and category_lower not in ESSENTIAL_CATEGORIES:
                return json.dumps(
                    {
                        "verdict": "denied",
                        "reason": "Survival stage: non-essential recurring expenses are blocked.",
                        "alternative_action": "Defer until runway ≥ 3 months or fund from existing Owner Pay surplus.",
                    },
                    indent=2,
                )

        if category_lower in ("opex", "operating", "business") or category_lower not in (
            "owner_pay",
            "profit",
            "tax",
            "investment",
        ):
            if self.expense_amount > self.available_opex_balance:
                shortfall = round(self.expense_amount - self.available_opex_balance, 2)
                return json.dumps(
                    {
                        "verdict": "denied",
                        "reason": f"OpEx bucket insufficient by ${shortfall:.2f}.",
                        "alternative_action": "Wait for next revenue allocation or reduce expense amount.",
                        "available_opex_balance": self.available_opex_balance,
                    },
                    indent=2,
                )

        if category_lower == "investment" and stage in ("Survival", "Stability"):
            return json.dumps(
                {
                    "verdict": "denied",
                    "reason": f"{stage} stage: investing blocked until Growth stage.",
                    "alternative_action": "Route to Tax Strategist to fund tax reserve first.",
                },
                indent=2,
            )

        return json.dumps(
            {
                "verdict": "approved",
                "reason": "Expense complies with stage rules and bucket availability.",
                "expense_amount": self.expense_amount,
                "financial_stage": stage,
                "description": self.expense_description or category_lower,
            },
            indent=2,
        )


if __name__ == "__main__":
    tool = ValidateExpenseAgainstRules(
        expense_amount=400,
        expense_category="software",
        available_opex_balance=1200,
        financial_stage="Survival",
        is_recurring=True,
        expense_description="Project management SaaS",
    )
    print(tool.run())
