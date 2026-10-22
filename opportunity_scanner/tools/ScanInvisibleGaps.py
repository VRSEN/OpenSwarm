import json

from agency_swarm.tools import BaseTool
from pydantic import Field

GAP_DEFINITIONS = {
    "convenience": "Time-for-money arbitrage: others pay to skip friction you can solve",
    "information": "Knowledge asymmetry: you know something the market hasn't priced",
    "connection": "Network access gaps: introductions others cannot make",
    "skill": "Execution gaps: skills you have that buyers lack",
    "attention": "Audience arbitrage: attention you can monetize faster than competitors",
}


class ScanInvisibleGaps(BaseTool):
    """Identifies arbitrage opportunities across five Invisible Gap types."""

    gap_types: list[str] = Field(default=["convenience", "information", "connection", "skill", "attention"])
    available_capital: float = Field(..., ge=0)
    max_days_to_payout: int = Field(default=7, ge=1, le=30)
    user_skills: list[str] = Field(default_factory=list)

    def run(self) -> str:
        valid = set(GAP_DEFINITIONS.keys())
        gaps = [g.lower().strip() for g in self.gap_types if g.lower().strip() in valid]
        if not gaps:
            return json.dumps({"error": f"gap_types must include: {list(valid)}"})

        opportunities = []
        for gap in gaps:
            opportunities.append(
                {
                    "gap_type": gap,
                    "definition": GAP_DEFINITIONS[gap],
                    "capital_required": min(self.available_capital, max(25, self.available_capital * 0.1)),
                    "max_days_to_payout": self.max_days_to_payout,
                    "skill_match": [s for s in self.user_skills if s] if gap == "skill" else [],
                    "research_action": f"Use WebSearchTool to find live {gap} gap in your market",
                }
            )

        return json.dumps(
            {
                "available_capital": self.available_capital,
                "max_days_to_payout": self.max_days_to_payout,
                "opportunities": opportunities,
                "next_step": "Score top candidates with ScoreMoneyVelocity",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        ScanInvisibleGaps(
            available_capital=175,
            user_skills=["web design", "automation"],
        ).run()
    )
