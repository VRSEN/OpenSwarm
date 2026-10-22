import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ExecuteDebtSnowballForAssets(BaseTool):
    """Prioritizes debt above APR threshold using surplus as guaranteed return."""

    debts: list[dict] = Field(..., description="List of {name, balance, apr, minimum_payment}")
    available_surplus: float = Field(..., ge=0)
    apr_threshold: float = Field(default=7.5, ge=0)

    def run(self) -> str:
        if not self.debts:
            return json.dumps({"error": "At least one debt required"})

        high_apr = [d for d in self.debts if float(d.get("apr", 0)) >= self.apr_threshold]
        high_apr.sort(key=lambda x: float(x.get("apr", 0)), reverse=True)

        if not high_apr:
            return json.dumps(
                {
                    "verdict": "no_action",
                    "reason": f"No debt at or above {self.apr_threshold}% APR threshold.",
                },
                indent=2,
            )

        target = high_apr[0]
        payment = min(self.available_surplus, float(target.get("balance", 0)))
        guaranteed_return = float(target.get("apr", 0))

        plan = []
        remaining = self.available_surplus
        for d in high_apr:
            if remaining <= 0:
                break
            pay = min(remaining, float(d.get("balance", 0)))
            plan.append(
                {
                    "name": d.get("name"),
                    "apr": d.get("apr"),
                    "payment": round(pay, 2),
                    "guaranteed_return_pct": d.get("apr"),
                }
            )
            remaining -= pay

        return json.dumps(
            {
                "verdict": "execute",
                "primary_target": target.get("name"),
                "guaranteed_return_pct": guaranteed_return,
                "snowball_plan": plan,
                "surplus_deployed": round(self.available_surplus - remaining, 2),
                "rule": "Paying high-APR debt IS a guaranteed return asset.",
            },
            indent=2,
        )


if __name__ == "__main__":
    tool = ExecuteDebtSnowballForAssets(
        debts=[
            {"name": "Credit Card", "balance": 4200, "apr": 9.2, "minimum_payment": 120},
            {"name": "Car Loan", "balance": 8000, "apr": 5.1, "minimum_payment": 310},
        ],
        available_surplus=400,
    )
    print(tool.run())
