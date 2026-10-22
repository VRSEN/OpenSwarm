import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class AssignDollarJobs(BaseTool):
    """Pre-assigns every expected dollar to a named job before it arrives."""

    expected_inflows: list[dict] = Field(..., description="List of {date, amount, source}")
    job_assignments: list[dict] = Field(..., description="List of {job_name, bucket, amount}")
    stability_fund_shortfall: float = Field(default=0, ge=0)

    def run(self) -> str:
        total_in = sum(float(i.get("amount", 0)) for i in self.expected_inflows)
        total_jobs = sum(float(j.get("amount", 0)) for j in self.job_assignments)

        if total_jobs > total_in + 0.01:
            return json.dumps(
                {"error": f"Jobs total ${total_jobs:.2f} exceeds expected inflows ${total_in:.2f}"},
            )

        unassigned = round(total_in - total_jobs, 2)
        priority_job = None
        if self.stability_fund_shortfall > 0 and unassigned > 0:
            assign = min(unassigned, self.stability_fund_shortfall)
            priority_job = {
                "job_name": "Stability Fund auto-fill",
                "bucket": "future",
                "amount": assign,
                "reason": "Mandatory before Life bucket jobs",
            }

        return json.dumps(
            {
                "expected_inflows_total": round(total_in, 2),
                "jobs_assigned_total": round(total_jobs, 2),
                "unassigned": unassigned,
                "priority_auto_job": priority_job,
                "job_ledger": self.job_assignments,
                "rule": "Every dollar has a job before arrival—no unassigned surplus to Life first.",
            },
            indent=2,
        )


if __name__ == "__main__":
    tool = AssignDollarJobs(
        expected_inflows=[{"date": "2026-06-15", "amount": 7200, "source": "client A"}],
        job_assignments=[
            {"job_name": "Rent", "bucket": "essentials", "amount": 1800},
            {"job_name": "Stability Fund", "bucket": "future", "amount": 1080},
        ],
        stability_fund_shortfall=5000,
    )
    print(tool.run())
