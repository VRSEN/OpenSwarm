import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class VetServiceProvider(BaseTool):
    """Combined vetting before engaging provider on velocity projects."""

    provider_name: str = Field(...)
    project_value: float = Field(..., gt=0)
    trust_score: float = Field(default=0, ge=0, le=100)
    min_trust_threshold: float = Field(default=70, ge=0, le=100)

    def run(self) -> str:
        if self.trust_score <= 0:
            return json.dumps(
                {
                    "verdict": "audit_required",
                    "reason": "Run AuditProviderBehavioralTrust first to obtain trust_score.",
                },
                indent=2,
            )

        if self.trust_score >= self.min_trust_threshold:
            verdict = "approved"
            risk = "low"
        elif self.trust_score >= 60:
            verdict = "conditional"
            risk = "medium"
        else:
            verdict = "denied"
            risk = "high"

        return json.dumps(
            {
                "provider_name": self.provider_name,
                "project_value": self.project_value,
                "trust_score": self.trust_score,
                "min_threshold": self.min_trust_threshold,
                "verdict": verdict,
                "economic_risk": risk,
                "note": "Character is an economic asset—reputation travels ahead of you.",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(VetServiceProvider(provider_name="QuickDev LLC", project_value=2000, trust_score=78).run())
