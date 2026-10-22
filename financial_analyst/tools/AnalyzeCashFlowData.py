import json
import os

import pandas as pd
from agency_swarm.tools import BaseTool
from pydantic import Field


class AnalyzeCashFlowData(BaseTool):
    """
    Parses a transaction CSV export and computes cash-flow KPIs for self-employed operators.
    """

    csv_path: str = Field(..., description="Path to transaction CSV file.")
    date_column: str = Field(default="date", description="Column name for transaction dates.")
    amount_column: str = Field(default="amount", description="Column name for amounts (positive=inflow).")
    category_column: str = Field(default="category", description="Column name for expense/income categories.")

    def run(self) -> str:
        if not os.path.isfile(self.csv_path):
            return json.dumps({"error": f"File not found: {self.csv_path}"})

        try:
            df = pd.read_csv(self.csv_path)
        except Exception as exc:
            return json.dumps({"error": f"Failed to read CSV: {exc}"})

        for col in (self.date_column, self.amount_column):
            if col not in df.columns:
                return json.dumps({"error": f"Column '{col}' not found. Available: {list(df.columns)}"})

        df[self.date_column] = pd.to_datetime(df[self.date_column], errors="coerce")
        df = df.dropna(subset=[self.date_column, self.amount_column])
        df["month"] = df[self.date_column].dt.to_period("M").astype(str)

        monthly = df.groupby("month")[self.amount_column].agg(["sum", "count"]).reset_index()
        monthly.columns = ["month", "net_flow", "transaction_count"]

        inflows = df[df[self.amount_column] > 0][self.amount_column].sum()
        outflows = abs(df[df[self.amount_column] < 0][self.amount_column].sum())
        net_margin = (inflows - outflows) / inflows * 100 if inflows > 0 else 0

        monthly_income = df[df[self.amount_column] > 0].groupby("month")[self.amount_column].sum()
        volatility = float(monthly_income.std() / monthly_income.mean()) if len(monthly_income) > 1 else 0

        top_expenses = {}
        if self.category_column in df.columns:
            expenses = df[df[self.amount_column] < 0].copy()
            expenses["abs_amount"] = expenses[self.amount_column].abs()
            top = (
                expenses.groupby(self.category_column)["abs_amount"]
                .sum()
                .sort_values(ascending=False)
                .head(5)
            )
            top_expenses = {k: round(v, 2) for k, v in top.items()}

        result = {
            "csv_path": self.csv_path,
            "months_analyzed": len(monthly),
            "total_inflows": round(float(inflows), 2),
            "total_outflows": round(float(outflows), 2),
            "net_margin_pct": round(net_margin, 2),
            "revenue_volatility_coefficient": round(volatility, 3),
            "volatility_warning": volatility > 0.35,
            "monthly_summary": monthly.to_dict(orient="records"),
            "top_expense_categories": top_expenses,
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    import tempfile

    sample = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    sample.write("date,amount,category\n")
    sample.write("2026-01-05,5000,client_payment\n")
    sample.write("2026-01-12,-120,software\n")
    sample.write("2026-02-01,6200,client_payment\n")
    sample.write("2026-02-15,-450,travel\n")
    sample.close()
    tool = AnalyzeCashFlowData(csv_path=sample.name)
    print(tool.run())
    os.unlink(sample.name)
