from __future__ import annotations

import json
from datetime import datetime, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field

from .common import compact_error, package_available


class MarketDataSnapshot(BaseTool):
    """
    Fetches stock price history and fundamentals from the best available configured source.

    Currently uses yfinance when installed. Agents should run TradingCapabilityDetector first
    to identify paid providers and IBKR availability for deeper market-data workflows.
    """

    symbols: list[str] = Field(..., description="Stock symbols to fetch, e.g. ['SPY', 'AAPL'].")
    period: str = Field(default="1y", description="yfinance period such as 1d, 5d, 1mo, 6mo, 1y, 5y.")
    interval: str = Field(default="1d", description="yfinance interval such as 1m, 5m, 1h, 1d, 1wk.")
    include_info: bool = Field(default=False, description="Include selected fundamental metadata.")

    def run(self):
        if not package_available("yfinance"):
            return json.dumps(
                {"ok": False, "error": "yfinance is not installed. Install requirements.txt to use this tool."},
                indent=2,
            )
        import yfinance as yf  # noqa: PLC0415

        output = {"ok": True, "checked_at": datetime.now(timezone.utc).isoformat(), "symbols": {}}
        try:
            for symbol in self.symbols:
                ticker = yf.Ticker(symbol.upper())
                hist = ticker.history(period=self.period, interval=self.interval, auto_adjust=False)
                summary = {
                    "rows": int(len(hist)),
                    "start": str(hist.index.min()) if not hist.empty else None,
                    "end": str(hist.index.max()) if not hist.empty else None,
                    "last_close": float(hist["Close"].dropna().iloc[-1]) if not hist.empty else None,
                    "last_volume": int(hist["Volume"].dropna().iloc[-1]) if not hist.empty and "Volume" in hist else None,
                    "recent_bars": hist.tail(5).reset_index().to_dict(orient="records") if not hist.empty else [],
                }
                if self.include_info:
                    info = ticker.get_info()
                    summary["info"] = {
                        key: info.get(key)
                        for key in (
                            "shortName",
                            "sector",
                            "industry",
                            "marketCap",
                            "trailingPE",
                            "forwardPE",
                            "dividendYield",
                            "beta",
                        )
                    }
                output["symbols"][symbol.upper()] = summary
            return json.dumps(output, indent=2, default=str)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": compact_error(exc)}, indent=2)
