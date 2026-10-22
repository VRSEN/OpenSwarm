import json
from datetime import datetime, timedelta, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field


class ScoreReputationCredit(BaseTool):
    """Computes behavioral credit score from self-trust and external reliability."""

    self_trust_events: list[dict] = Field(default_factory=list)
    external_reliability_events: list[dict] = Field(default_factory=list)
    lookback_days: int = Field(default=90, ge=1)

    def run(self) -> str:
        if not self.self_trust_events and not self.external_reliability_events:
            return json.dumps({"error": "Provide at least one event in either list"})

        self_score = _rate_events(self.self_trust_events, "kept_commitment")
        external_score = _rate_events(self.external_reliability_events, "delivered")
        total = self_score * 0.4 + external_score * 0.6

        tier = "Platinum" if total >= 90 else "Gold" if total >= 75 else "Silver" if total >= 60 else "Bronze"

        return json.dumps(
            {
                "reputation_credit_score": round(total, 1),
                "tier": tier,
                "self_trust_component": round(self_score, 1),
                "external_reliability_component": round(external_score, 1),
                "lookback_days": self.lookback_days,
                "travels_ahead_summary": (
                    f"Reputation Credit {total:.0f}/100 ({tier})—"
                    f"behavioral trust evidence from {len(self.self_trust_events)} self-events "
                    f"and {len(self.external_reliability_events)} external events."
                ),
            },
            indent=2,
        )


def _rate_events(events: list, key: str) -> float:
    if not events:
        return 50.0
    kept = sum(1 for e in events if e.get(key, False))
    return (kept / len(events)) * 100


if __name__ == "__main__":
    print(
        ScoreReputationCredit(
            self_trust_events=[
                {"kept_commitment": True},
                {"kept_commitment": True},
                {"kept_commitment": False},
            ],
            external_reliability_events=[
                {"provider": "DevCo", "delivered": True},
                {"provider": "DevCo", "delivered": True},
            ],
        ).run()
    )
