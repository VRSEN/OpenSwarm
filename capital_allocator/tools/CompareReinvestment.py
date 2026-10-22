import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.omni_wealth import compare_reinvestment


class CompareReinvestment(BaseTool):
    """Compare putting a dollar into the business vs an outside bet."""

    capital: float = Field(..., gt=0)
    internal_return_pct: float = Field(..., ge=0, description="Expected % return if invested in the business")
    external_return_pct: float = Field(..., ge=0, description="Expected % return of the outside option")
    days: int = Field(default=30, ge=1)
    track_record: str = Field(default="thin", description="none, thin, or proven")

    def run(self) -> str:
        return json.dumps(
            compare_reinvestment(
                self.capital,
                self.internal_return_pct,
                self.external_return_pct,
                days=self.days,
                track_record=self.track_record,
            ),
            indent=2,
        )


if __name__ == "__main__":
    print(CompareReinvestment(capital=2000, internal_return_pct=40, external_return_pct=12).run())
