import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class GenerateSilentDashboard(BaseTool):
    """
    Minimalist Silent Dashboard—exactly 3 KPIs plus one identity line.
    No stimulation. No extra charts.
    """

    stability_fund_pct: float = Field(...)
    money_velocity_score: float = Field(...)
    reputation_credit: float = Field(...)
    stage: str = Field(default="Stability")
    solitude_mode: bool = Field(default=False)

    def run(self) -> str:
        kpis = [
            {"label": "Stability Fund", "value": f"{self.stability_fund_pct:.0f}%", "unit": "funded"},
            {"label": "Money Velocity", "value": f"{self.money_velocity_score:.1f}", "unit": "score"},
            {"label": "Reputation Credit", "value": f"{self.reputation_credit:.0f}", "unit": "/100"},
        ]

        identity_line = "You are an architect who protects their future."

        suppressed = []
        if self.solitude_mode:
            suppressed = ["consumption KPIs", "promotional summaries", "non-essential agent prompts"]

        return json.dumps(
            {
                "dashboard_type": "silent",
                "max_kpis": 3,
                "stage": self.stage,
                "kpis": kpis,
                "identity_line": identity_line,
                "solitude_mode": self.solitude_mode,
                "suppressed_in_solitude": suppressed,
                "design_rule": "Focus over stimulation—no charts unless explicitly requested.",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        GenerateSilentDashboard(
            stability_fund_pct=67,
            money_velocity_score=8.4,
            reputation_credit=82,
            stage="Skill Stacking",
        ).run()
    )
