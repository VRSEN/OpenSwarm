import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class Enforce156520Allocation(BaseTool):
    """Splits gross inflow into Future 15%, Essentials 65%, Life 20%."""

    gross_inflow: float = Field(..., gt=0)
    future_pct: float = Field(default=15, ge=0, le=100)
    essentials_pct: float = Field(default=65, ge=0, le=100)
    life_pct: float = Field(default=20, ge=0, le=100)

    def run(self) -> str:
        total = self.future_pct + self.essentials_pct + self.life_pct
        if abs(total - 100) > 0.01:
            return json.dumps({"error": f"Percentages must sum to 100; got {total}"})

        buckets = {
            "future": round(self.gross_inflow * self.future_pct / 100, 2),
            "essentials": round(self.gross_inflow * self.essentials_pct / 100, 2),
            "life": round(self.gross_inflow * self.life_pct / 100, 2),
        }
        delta = round(self.gross_inflow - sum(buckets.values()), 2)
        if delta:
            buckets["future"] = round(buckets["future"] + delta, 2)

        return json.dumps(
            {
                "gross_inflow": self.gross_inflow,
                "principle": "15/65/20 — assign jobs before spending",
                "allocations": buckets,
                "transfer_checklist": [
                    f"${buckets['future']:.2f} → Future (Stability Fund, debt snowball, investments)",
                    f"${buckets['essentials']:.2f} → Essentials (non-negotiable costs)",
                    f"${buckets['life']:.2f} → Life (discretionary; 72-hour pause applies)",
                ],
            },
            indent=2,
        )


if __name__ == "__main__":
    print(Enforce156520Allocation(gross_inflow=6500).run())
