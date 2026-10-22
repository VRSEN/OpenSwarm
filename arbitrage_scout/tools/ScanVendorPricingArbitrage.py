import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ScanVendorPricingArbitrage(BaseTool):
    """
    Structures a vendor pricing arbitrage analysis for the Arbitrage Scout agent.
    The agent should use WebSearchTool to find alternatives, then populate savings estimates.
    Returns a framework with payback calculation for the agent to fill from search results.
    """

    service_category: str = Field(..., description="e.g., payment processing, accounting software, cloud hosting.")
    current_monthly_cost: float = Field(..., gt=0, description="Current monthly spend with vendor.")
    current_vendor: str = Field(..., description="Name of current vendor.")
    annual_contract: bool = Field(default=False, description="True if locked into annual contract.")
    estimated_alternative_monthly_cost: float = Field(
        default=0,
        ge=0,
        description="Best alternative monthly cost found via research (0 if not yet researched).",
    )
    switch_setup_cost: float = Field(default=0, ge=0, description="One-time cost to switch vendors.")
    switch_effort_hours: float = Field(default=2, ge=0, description="Estimated hours to complete switch.")

    def run(self) -> str:
        monthly_savings = max(self.current_monthly_cost - self.estimated_alternative_monthly_cost, 0)
        payback_months = (
            self.switch_setup_cost / monthly_savings if monthly_savings > 0 else None
        )
        annual_savings = monthly_savings * 12

        friction_score = "low"
        if self.annual_contract:
            friction_score = "high"
        elif self.switch_effort_hours > 8:
            friction_score = "medium"

        research_prompt = (
            f"Search for {self.service_category} alternatives to {self.current_vendor} "
            f"for self-employed users. Current cost: ${self.current_monthly_cost}/mo. "
            f"Find 3 alternatives with pricing, features, and migration friction."
        )

        result = {
            "service_category": self.service_category,
            "current_vendor": self.current_vendor,
            "current_monthly_cost": self.current_monthly_cost,
            "annual_contract": self.annual_contract,
            "estimated_alternative_monthly_cost": self.estimated_alternative_monthly_cost,
            "monthly_savings": round(monthly_savings, 2),
            "annual_savings": round(annual_savings, 2),
            "switch_setup_cost": self.switch_setup_cost,
            "payback_months": round(payback_months, 1) if payback_months else "N/A—research alternatives first",
            "switch_friction": friction_score,
            "switch_effort_hours": self.switch_effort_hours,
            "next_step": "Use WebSearchTool with the research_prompt below, then re-run with estimated_alternative_monthly_cost.",
            "research_prompt": research_prompt,
            "alternatives": [],
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = ScanVendorPricingArbitrage(
        service_category="payment processing",
        current_monthly_cost=180,
        current_vendor="Stripe",
        estimated_alternative_monthly_cost=95,
        switch_setup_cost=0,
    )
    print(tool.run())
