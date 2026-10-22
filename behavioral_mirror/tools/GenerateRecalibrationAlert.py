import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import detect_drift_for_recalibration


class GenerateRecalibrationAlert(BaseTool):
    """Detect drift from 15/65/20 or pause rule; issue identity-framed recalibration alert."""

    essentials_pct: float = Field(..., ge=0, le=100)
    life_bucket_pct: float = Field(default=20.0, ge=0, le=100)
    pause_breaches_recent: int = Field(default=0, ge=0)
    target_essentials_pct: float = Field(default=65.0, ge=0, le=100)

    def run(self) -> str:
        payload = detect_drift_for_recalibration(
            essentials_pct=self.essentials_pct,
            target_essentials_pct=self.target_essentials_pct,
            pause_breaches_recent=self.pause_breaches_recent,
            life_bucket_over_pct=self.life_bucket_pct,
        )
        if not payload:
            return json.dumps(
                {
                    "alert_required": False,
                    "message": "Machine within architect standards. No recalibration needed.",
                },
                indent=2,
            )
        payload["alert_required"] = True
        payload["identity_frame"] = (
            "Return to your principles before drift affects public creditworthiness."
        )
        return json.dumps(payload, indent=2)


if __name__ == "__main__":
    print(GenerateRecalibrationAlert(essentials_pct=71, pause_breaches_recent=1).run())
