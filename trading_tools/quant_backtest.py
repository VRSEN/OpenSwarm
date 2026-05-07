from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field

from .common import compact_error, package_available


class QuantBacktest(BaseTool):
    """
    Runs a simple long-only or long/flat moving-average momentum backtest for a stock symbol.

    This is a fast first-pass research tool for idea triage, not a production execution engine.
    """

    symbol: str = Field(..., description="Stock symbol to backtest.")
    period: str = Field(default="5y", description="Data period, e.g. 1y, 2y, 5y, 10y.")
    fast_window: int = Field(default=20, description="Fast moving average window.")
    slow_window: int = Field(default=100, description="Slow moving average window.")
    long_flat: bool = Field(default=True, description="If true, strategy is long or cash. If false, long or short.")
    transaction_cost_bps: float = Field(default=2.0, description="One-way transaction cost in basis points.")

    def run(self):
        if not package_available("yfinance"):
            return json.dumps(
                {"ok": False, "error": "yfinance is not installed. Install requirements.txt to use this tool."},
                indent=2,
            )
        try:
            import numpy as np  # noqa: PLC0415
            import yfinance as yf  # noqa: PLC0415

            if self.fast_window <= 1 or self.slow_window <= self.fast_window:
                return json.dumps(
                    {"ok": False, "error": "Require slow_window > fast_window > 1."},
                    indent=2,
                )
            data = yf.Ticker(self.symbol.upper()).history(period=self.period, interval="1d", auto_adjust=True)
            if data.empty or len(data) < self.slow_window + 10:
                return json.dumps({"ok": False, "error": "Not enough price history returned."}, indent=2)

            close = data["Close"].dropna()
            returns = close.pct_change().fillna(0.0)
            fast = close.rolling(self.fast_window).mean()
            slow = close.rolling(self.slow_window).mean()
            raw_signal = (fast > slow).astype(float)
            if not self.long_flat:
                raw_signal = raw_signal.replace(0.0, -1.0)
            signal = raw_signal.shift(1).fillna(0.0)
            turnover = signal.diff().abs().fillna(0.0)
            cost = turnover * (self.transaction_cost_bps / 10000.0)
            strategy_returns = signal * returns - cost
            equity = (1 + strategy_returns).cumprod()
            benchmark = (1 + returns).cumprod()
            years = max((close.index[-1] - close.index[0]).days / 365.25, 0.001)
            total_return = float(equity.iloc[-1] - 1)
            benchmark_return = float(benchmark.iloc[-1] - 1)
            cagr = float(equity.iloc[-1] ** (1 / years) - 1)
            ann_vol = float(strategy_returns.std() * math.sqrt(252))
            sharpe = float((strategy_returns.mean() * 252) / ann_vol) if ann_vol > 0 else None
            drawdown = equity / equity.cummax() - 1
            max_drawdown = float(drawdown.min())
            trades = int((turnover > 0).sum())
            win_rate = float((strategy_returns[strategy_returns != 0] > 0).mean())

            return json.dumps(
                {
                    "ok": True,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "symbol": self.symbol.upper(),
                    "period": self.period,
                    "fast_window": self.fast_window,
                    "slow_window": self.slow_window,
                    "mode": "long_flat" if self.long_flat else "long_short",
                    "transaction_cost_bps": self.transaction_cost_bps,
                    "rows": int(len(close)),
                    "start": str(close.index[0]),
                    "end": str(close.index[-1]),
                    "strategy": {
                        "total_return": total_return,
                        "cagr": cagr,
                        "annualized_volatility": ann_vol,
                        "sharpe": sharpe,
                        "max_drawdown": max_drawdown,
                        "trades": trades,
                        "win_rate_nonzero_days": win_rate if not np.isnan(win_rate) else None,
                    },
                    "benchmark_buy_hold": {"total_return": benchmark_return},
                    "current_signal": "long" if signal.iloc[-1] > 0 else ("short" if signal.iloc[-1] < 0 else "cash"),
                },
                indent=2,
                default=str,
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": compact_error(exc)}, indent=2)
