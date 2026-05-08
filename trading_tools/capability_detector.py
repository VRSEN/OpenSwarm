from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field

from .common import env_present, ibkr_settings, package_available, socket_open


class TradingCapabilityDetector(BaseTool):
    """
    Detects currently available trading, market-data, research, and sentiment capabilities.

    Use this before any trading workflow to discover which paid APIs, data subscriptions,
    Python packages, and IBKR gateway/TWS connections are actually available at runtime.
    """

    include_environment_names: bool = Field(
        default=True,
        description="If true, include the names of detected environment variables without exposing their secret values.",
    )
    test_ibkr_socket: bool = Field(
        default=True,
        description="If true, test whether the configured IBKR host and port accept TCP connections.",
    )

    def run(self):
        settings = ibkr_settings()
        packages = {
            "ib_insync": package_available("ib_insync"),
            "yfinance": package_available("yfinance"),
            "pandas": package_available("pandas"),
            "numpy": package_available("numpy"),
            "scipy": package_available("scipy"),
            "statsmodels": package_available("statsmodels"),
            "sklearn": package_available("sklearn"),
            "ta": package_available("ta"),
            "transformers": package_available("transformers"),
            "vaderSentiment": package_available("vaderSentiment"),
        }
        providers = {
            "IBKR": {
                "configured": True,
                "host": settings.host,
                "port": settings.port,
                "client_id": settings.client_id,
                "account_configured": bool(settings.account),
                "readonly_default": settings.readonly,
                "ib_insync_installed": packages["ib_insync"],
                "socket_reachable": socket_open(settings.host, settings.port) if self.test_ibkr_socket else None,
            },
            "Polygon": {"api_key_present": env_present("POLYGON_API_KEY")},
            "Alpha Vantage": {"api_key_present": env_present("ALPHAVANTAGE_API_KEY")},
            "Finnhub": {"api_key_present": env_present("FINNHUB_API_KEY")},
            "FMP": {"api_key_present": env_present("FMP_API_KEY")},
            "Tiingo": {"api_key_present": env_present("TIINGO_API_KEY")},
            "NewsAPI": {"api_key_present": env_present("NEWSAPI_API_KEY")},
            "OpenAI": {"api_key_present": env_present("OPENAI_API_KEY")},
        }
        research_env_names = [
            name
            for name in os.environ
            if any(token in name.upper() for token in ("RESEARCH", "NEWS", "SENTIMENT", "MARKETDATA", "DATA_API"))
        ]
        payload = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "packages": packages,
            "providers": providers,
            "detected_research_environment_variables": sorted(research_env_names)
            if self.include_environment_names
            else [],
            "next_steps": [
                "Start Trader Workstation or IB Gateway and enable API access if IBKR socket is not reachable.",
                "Install missing packages from requirements.txt if a requested workflow depends on them.",
                "Run IBKRAccountSnapshot to verify live account, entitlements, positions, and market data access.",
            ],
        }
        return json.dumps(payload, indent=2, default=str)
