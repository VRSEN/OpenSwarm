import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class EnforceProfitFirstAllocation(BaseTool):
    """
    Splits incoming revenue into Profit, Tax, Owner Pay, and OpEx buckets
    using configurable Profit First percentages.
    """

    gross_revenue: float = Field(..., gt=0, description="Incoming payment or monthly revenue total.")
    profit_pct: float = Field(default=5, ge=0, le=100, description="Profit bucket percentage.")
    tax_pct: float = Field(default=15, ge=0, le=100, description="Tax bucket percentage.")
    owner_pay_pct: float = Field(default=50, ge=0, le=100, description="Owner Pay bucket percentage.")
    opex_pct: float = Field(default=30, ge=0, le=100, description="Operating expense bucket percentage.")

    def run(self) -> str:
        total_pct = self.profit_pct + self.tax_pct + self.owner_pay_pct + self.opex_pct
        if abs(total_pct - 100) > 0.01:
            return json.dumps({"error": f"Percentages must sum to 100; got {total_pct}."})

        buckets = {
            "profit": round(self.gross_revenue * self.profit_pct / 100, 2),
            "tax": round(self.gross_revenue * self.tax_pct / 100, 2),
            "owner_pay": round(self.gross_revenue * self.owner_pay_pct / 100, 2),
            "opex": round(self.gross_revenue * self.opex_pct / 100, 2),
        }
        allocated = sum(buckets.values())
        rounding_delta = round(self.gross_revenue - allocated, 2)
        if rounding_delta != 0:
            buckets["opex"] = round(buckets["opex"] + rounding_delta, 2)

        transfers = [
            f"Transfer ${buckets['profit']:.2f} → Profit account ({self.profit_pct}%)",
            f"Transfer ${buckets['tax']:.2f} → Tax reserve account ({self.tax_pct}%)",
            f"Transfer ${buckets['owner_pay']:.2f} → Owner Pay account ({self.owner_pay_pct}%)",
            f"Transfer ${buckets['opex']:.2f} → OpEx account ({self.opex_pct}%)",
        ]

        result = {
            "gross_revenue": self.gross_revenue,
            "percentages": {
                "profit": self.profit_pct,
                "tax": self.tax_pct,
                "owner_pay": self.owner_pay_pct,
                "opex": self.opex_pct,
            },
            "allocations": buckets,
            "transfer_checklist": transfers,
            "rule": "Only Owner Pay is available for personal spending.",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = EnforceProfitFirstAllocation(gross_revenue=8000)
    print(tool.run())
