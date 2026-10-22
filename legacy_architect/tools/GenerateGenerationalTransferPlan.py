import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class GenerateGenerationalTransferPlan(BaseTool):
    """Summarizes generational transfer plan with heir checklist."""

    heir_names: list[str] = Field(...)
    assets_documented: list[str] = Field(default_factory=list)
    estimated_step_up_benefit: float = Field(..., ge=0)

    def run(self) -> str:
        if not self.heir_names:
            return json.dumps({"error": "At least one heir name required"})

        checklist = [
            "Step-Up in Basis documentation stored in Sovereign Vault",
            "Beneficiary designations updated on all accounts",
            "Buy-Borrow-Die strategy reviewed with estate attorney",
            "Heir access instructions stored separately from vault key",
            "Annual FMV appraisal schedule for documented assets",
        ]

        return json.dumps(
            {
                "heirs": self.heir_names,
                "assets_documented": self.assets_documented,
                "estimated_step_up_benefit": self.estimated_step_up_benefit,
                "heir_checklist": checklist,
                "disclaimer": "Legal estate planning required—this is a documentation framework only.",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        GenerateGenerationalTransferPlan(
            heir_names=["Jordan", "Alex"],
            assets_documented=["rental_a_basis", "ip_portfolio_basis"],
            estimated_step_up_benefit=135000,
        ).run()
    )
