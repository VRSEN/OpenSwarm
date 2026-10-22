import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class DocumentStepUpInBasis(BaseTool):
    """Creates structured Step-Up in Basis record for heirs."""

    asset_name: str = Field(...)
    acquisition_date: str = Field(...)
    cost_basis: float = Field(..., ge=0)
    current_fair_market_value: float = Field(..., ge=0)
    documentation_refs: list[str] = Field(default_factory=list)
    heir_designation: str = Field(default="")

    def run(self) -> str:
        step_up_benefit = max(self.current_fair_market_value - self.cost_basis, 0)

        return json.dumps(
            {
                "asset_name": self.asset_name,
                "acquisition_date": self.acquisition_date,
                "cost_basis": self.cost_basis,
                "current_fmv": self.current_fair_market_value,
                "estimated_step_up_benefit_at_death": round(step_up_benefit, 2),
                "documentation_refs": self.documentation_refs,
                "heir_designation": self.heir_designation or "To be designated",
                "next_step": "Store in EncryptSovereignVault",
                "disclaimer": "Estate law varies—confirm with estate attorney.",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        DocumentStepUpInBasis(
            asset_name="Primary rental",
            acquisition_date="2019-06-01",
            cost_basis=185000,
            current_fair_market_value=320000,
            documentation_refs=["appraisal_2026.pdf"],
        ).run()
    )
