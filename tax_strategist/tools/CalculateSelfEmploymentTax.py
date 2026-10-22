import json

from agency_swarm.tools import BaseTool
from pydantic import Field

# 2026 US federal constants (verify with tax professional)
SS_WAGE_BASE = 176_100
SS_RATE = 0.124
MEDICARE_RATE = 0.029
ADDITIONAL_MEDICARE_THRESHOLD = 200_000
ADDITIONAL_MEDICARE_RATE = 0.009
SE_NET_MULTIPLIER = 0.9235


class CalculateSelfEmploymentTax(BaseTool):
    """
    Estimates US self-employment tax (Social Security + Medicare) on net self-employment profit.
    """

    net_profit: float = Field(..., ge=0, description="Annual or YTD net self-employment income.")
    period: str = Field(default="annual", description="annual or ytd.")
    w2_wages: float = Field(default=0, ge=0, description="W-2 wages that count toward SS wage base.")

    def run(self) -> str:
        taxable_se = self.net_profit * SE_NET_MULTIPLIER

        ss_taxable = max(min(taxable_se, SS_WAGE_BASE - self.w2_wages), 0)
        ss_tax = ss_taxable * SS_RATE

        medicare_tax = taxable_se * MEDICARE_RATE
        additional_medicare = 0.0
        if taxable_se + self.w2_wages > ADDITIONAL_MEDICARE_THRESHOLD:
            excess = taxable_se + self.w2_wages - ADDITIONAL_MEDICARE_THRESHOLD
            additional_medicare = min(excess, taxable_se) * ADDITIONAL_MEDICARE_RATE

        total_se_tax = ss_tax + medicare_tax + additional_medicare
        effective_rate = (total_se_tax / self.net_profit * 100) if self.net_profit > 0 else 0

        result = {
            "period": self.period,
            "net_profit": self.net_profit,
            "taxable_se_income": round(taxable_se, 2),
            "social_security_tax": round(ss_tax, 2),
            "medicare_tax": round(medicare_tax, 2),
            "additional_medicare_tax": round(additional_medicare, 2),
            "total_se_tax": round(total_se_tax, 2),
            "effective_se_rate_pct": round(effective_rate, 2),
            "note": "Estimate only. Confirm with CPA. Income tax is separate.",
            "constants_year": 2026,
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = CalculateSelfEmploymentTax(net_profit=95000, w2_wages=0)
    print(tool.run())
