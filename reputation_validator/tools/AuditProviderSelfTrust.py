import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import SelfTrustEvent, compute_self_trust_index


class AuditProviderSelfTrust(BaseTool):
    """Pillar 2 for providers — promises-to-self vs actual delivery pattern."""

    self_commitments: list[dict] = Field(
        default_factory=list,
        description="{promised_date, actual_date, kept (bool)}",
    )
    provider_name: str = Field(default="provider")

    def run(self) -> str:
        events = [
            SelfTrustEvent(
                kept_commitment=c.get("kept", c.get("kept_commitment", False)),
                event_type="self_deadline",
            )
            for c in self.self_commitments
        ]
        result = compute_self_trust_index(events)
        downgrade = result["self_trust_index"] < 60
        return json.dumps(
            {
                "provider_name": self.provider_name,
                "self_trust_index": result["self_trust_index"],
                "automatic_vetting_downgrade": downgrade,
                "verdict_note": (
                    "High self-trust breach rate—downgrade even if public reviews look fine."
                    if downgrade
                    else "Self-trust within acceptable range."
                ),
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        AuditProviderSelfTrust(
            provider_name="DevCo",
            self_commitments=[{"kept": True}, {"kept": False}, {"kept": False}],
        ).run()
    )
