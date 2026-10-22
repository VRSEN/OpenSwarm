import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from agency_swarm.tools import BaseTool
from pydantic import Field


class GenerateReputationCreditDashboard(BaseTool):
    """Renders Reputation Credit score history summary and optional chart."""

    score_history: list[dict] = Field(...)
    provider_audits: list[dict] = Field(default_factory=list)
    output_dir: str = Field(default="")

    def run(self) -> str:
        if not self.score_history:
            return json.dumps({"error": "score_history required"})

        scores = [
            float(h.get("reputation_credit_score", h.get("current_score", 0)))
            for h in self.score_history
            if h.get("reputation_credit_score") or h.get("current_score")
        ]
        current = scores[-1] if scores else 0
        trend = "rising" if len(scores) >= 2 and scores[-1] > scores[-2] else "stable"

        out_dir = Path(self.output_dir) if self.output_dir else Path(__file__).resolve().parent.parent / "files"
        out_dir.mkdir(parents=True, exist_ok=True)
        chart_path = ""

        if len(scores) >= 2:
            chart_path = str(out_dir / "reputation_credit_trend.png")
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.plot(range(len(scores)), scores, color="#64748b", linewidth=1.5)
            ax.set_ylim(0, 100)
            ax.set_title("Reputation Credit", fontsize=10)
            ax.set_ylabel("Score")
            fig.tight_layout()
            fig.savefig(chart_path, dpi=100)
            plt.close(fig)

        provider_summary = [
            {"provider": p.get("provider_name"), "verdict": p.get("verdict"), "trust_score": p.get("trust_score")}
            for p in self.provider_audits
        ]

        return json.dumps(
            {
                "current_score": current,
                "trend": trend,
                "readings_count": len(scores),
                "provider_audits": provider_summary,
                "chart_path": chart_path or "none—insufficient history",
                "travels_ahead_line": f"Reputation Credit {current:.0f}/100 travels ahead of you in negotiations.",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        GenerateReputationCreditDashboard(
            score_history=[{"reputation_credit_score": 72}, {"reputation_credit_score": 78}, {"reputation_credit_score": 82}],
        ).run()
    )
