import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from agency_swarm.tools import BaseTool
from pydantic import Field


class GenerateFinancialDashboard(BaseTool):
    """
    Creates PNG visualization charts from KPI data and saves them to the agent files folder.
    """

    kpi_data: dict = Field(..., description="Metrics dict from AnalyzeCashFlowData or manual entry.")
    chart_types: list[str] = Field(
        default=["runway", "allocation", "income_trend"],
        description="Charts to generate: runway, allocation, income_trend.",
    )
    output_dir: str = Field(default="", description="Output directory; defaults to agent files folder.")

    def run(self) -> str:
        if not self.kpi_data:
            return json.dumps({"error": "kpi_data cannot be empty."})

        out_dir = Path(self.output_dir) if self.output_dir else Path(__file__).resolve().parent.parent / "files"
        out_dir.mkdir(parents=True, exist_ok=True)

        generated = []

        if "runway" in self.chart_types:
            cash = self.kpi_data.get("liquid_cash", self.kpi_data.get("adjusted_cash", 0))
            burn = self.kpi_data.get("monthly_burn", self.kpi_data.get("monthly_expenses", 1))
            runway = cash / burn if burn > 0 else 0
            path = out_dir / "runway_chart.png"
            fig, ax = plt.subplots(figsize=(6, 4))
            colors = ["#ef4444" if runway < 3 else "#f59e0b" if runway < 6 else "#22c55e"]
            ax.barh(["Runway (months)"], [runway], color=colors)
            ax.axvline(x=3, color="#ef4444", linestyle="--", alpha=0.7, label="Survival threshold")
            ax.axvline(x=6, color="#f59e0b", linestyle="--", alpha=0.7, label="Stability threshold")
            ax.axvline(x=12, color="#22c55e", linestyle="--", alpha=0.7, label="Sovereignty threshold")
            ax.set_xlabel("Months")
            ax.legend(fontsize=8)
            ax.set_title("Cash Runway")
            fig.tight_layout()
            fig.savefig(path, dpi=120)
            plt.close(fig)
            generated.append({"chart": "runway", "path": str(path), "caption": f"{runway:.1f} months runway"})

        if "allocation" in self.chart_types:
            alloc = self.kpi_data.get("allocations") or self.kpi_data.get("allocation_pct")
            if alloc:
                path = out_dir / "allocation_chart.png"
                fig, ax = plt.subplots(figsize=(6, 4))
                labels = list(alloc.keys())
                values = list(alloc.values())
                ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
                ax.set_title("Profit First Allocation")
                fig.tight_layout()
                fig.savefig(path, dpi=120)
                plt.close(fig)
                generated.append({"chart": "allocation", "path": str(path), "caption": "Bucket allocation split"})

        if "income_trend" in self.chart_types:
            monthly = self.kpi_data.get("monthly_summary", [])
            if monthly:
                path = out_dir / "income_trend_chart.png"
                months = [m.get("month", "") for m in monthly]
                flows = [m.get("net_flow", 0) for m in monthly]
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.plot(months, flows, marker="o", color="#3b82f6")
                ax.axhline(y=0, color="#94a3b8", linewidth=0.8)
                ax.set_title("Monthly Net Cash Flow")
                ax.set_ylabel("Net Flow ($)")
                plt.xticks(rotation=45, ha="right")
                fig.tight_layout()
                fig.savefig(path, dpi=120)
                plt.close(fig)
                generated.append({"chart": "income_trend", "path": str(path), "caption": "Monthly net flow trend"})

        if not generated:
            return json.dumps({"error": "No charts generated—check chart_types and kpi_data fields."})

        return json.dumps({"charts_generated": len(generated), "files": generated, "output_dir": str(out_dir)}, indent=2)


if __name__ == "__main__":
    tool = GenerateFinancialDashboard(
        kpi_data={
            "liquid_cash": 18000,
            "monthly_burn": 4500,
            "allocations": {"profit": 5, "tax": 15, "owner_pay": 50, "opex": 30},
            "monthly_summary": [
                {"month": "2026-01", "net_flow": 3200},
                {"month": "2026-02", "net_flow": 4100},
                {"month": "2026-03", "net_flow": 2800},
            ],
        },
    )
    print(tool.run())
