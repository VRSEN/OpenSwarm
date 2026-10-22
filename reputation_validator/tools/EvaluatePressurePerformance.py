import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import PressurePerformanceInput, score_pressure_performance


class EvaluatePressurePerformance(BaseTool):
    """Pillar 3 — crisis composure, failure response, private standards."""

    crisis_events: int = Field(default=0, ge=0)
    crisis_passed: int = Field(default=0, ge=0)
    repeat_failure_modes: int = Field(default=0, ge=0)
    private_job_count: int = Field(default=0, ge=0)
    private_on_time_rate_pct: float = Field(default=100.0, ge=0, le=100)
    subject_name: str = Field(default="user")

    def run(self) -> str:
        score = score_pressure_performance(
            PressurePerformanceInput(
                crisis_events=self.crisis_events,
                crisis_passed=self.crisis_passed,
                repeat_failure_modes=self.repeat_failure_modes,
                private_job_count=self.private_job_count,
                private_on_time_rate=self.private_on_time_rate_pct,
            )
        )
        return json.dumps(
            {
                "subject_name": self.subject_name,
                "pressure_performance_score": round(score, 1),
                "pillar": "pressure_performance",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(EvaluatePressurePerformance(crisis_events=2, crisis_passed=2, private_job_count=4).run())
