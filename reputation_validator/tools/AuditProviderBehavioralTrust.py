import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class AuditProviderBehavioralTrust(BaseTool):
    """Vets service provider on consistency and follow-through."""

    provider_name: str = Field(...)
    engagements: list[dict] = Field(..., description="List of {date, promised, delivered, on_time}")
    references_verified: int = Field(default=0, ge=0)

    def run(self) -> str:
        if not self.engagements:
            return json.dumps({"error": "At least one engagement required"})

        delivered = sum(1 for e in self.engagements if e.get("delivered", False))
        on_time = sum(1 for e in self.engagements if e.get("on_time", False))
        total = len(self.engagements)

        delivery_rate = delivered / total * 100
        on_time_rate = on_time / total * 100
        ref_bonus = min(self.references_verified * 5, 15)
        trust_score = min(delivery_rate * 0.6 + on_time_rate * 0.4 + ref_bonus, 100)

        flags = []
        if delivery_rate < 80:
            flags.append("Delivery rate below 80%")
        if on_time_rate < 70:
            flags.append("On-time rate below 70%")

        verdict = "hire" if trust_score >= 75 and not flags else "monitor" if trust_score >= 60 else "avoid"

        return json.dumps(
            {
                "provider_name": self.provider_name,
                "trust_score": round(trust_score, 1),
                "delivery_rate_pct": round(delivery_rate, 1),
                "on_time_rate_pct": round(on_time_rate, 1),
                "references_verified": self.references_verified,
                "flags": flags,
                "verdict": verdict,
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        AuditProviderBehavioralTrust(
            provider_name="QuickDev LLC",
            engagements=[
                {"date": "2026-01", "promised": "API build", "delivered": True, "on_time": True},
                {"date": "2026-03", "promised": "Fix bugs", "delivered": True, "on_time": False},
            ],
            references_verified=2,
        ).run()
    )
