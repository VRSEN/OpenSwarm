import json
from datetime import datetime, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field

SUPPRESSED_IN_SOLITUDE = [
    "consumption_opportunity_scanner",
    "promotional_summaries",
    "non_essential_notifications",
    "life_bucket_suggestions",
]

ALLOWED_IN_SOLITUDE = [
    "silent_dashboard",
    "156520_allocation",
    "stability_fund_tracking",
    "skill_stacking_progress",
    "velocity_tracker_readonly",
]


class CheckSolitudeModeGate(BaseTool):
    """Returns allowed/suppressed modules during 6-Month Focus Season."""

    solitude_mode_active: bool = Field(default=False)
    focus_season_start: str = Field(default="")
    focus_season_months: int = Field(default=6, ge=1, le=12)

    def run(self) -> str:
        days_remaining = None
        if self.solitude_mode_active and self.focus_season_start:
            try:
                start = datetime.fromisoformat(self.focus_season_start.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - start).days
                total_days = self.focus_season_months * 30
                days_remaining = max(total_days - elapsed, 0)
            except ValueError:
                days_remaining = self.focus_season_months * 30

        return json.dumps(
            {
                "solitude_mode_active": self.solitude_mode_active,
                "focus_season_months": self.focus_season_months,
                "days_remaining": days_remaining,
                "allowed_modules": ALLOWED_IN_SOLITUDE if self.solitude_mode_active else "all",
                "suppressed_modules": SUPPRESSED_IN_SOLITUDE if self.solitude_mode_active else [],
                "purpose": "6-Month Focus Season—deep work and system construction over consumption",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(CheckSolitudeModeGate(solitude_mode_active=True, focus_season_start="2026-01-01").run())
