# Trading Portfolio Swarm

This fork of OpenSwarm is configured as a multi-agent trading and portfolio-management team.

It coordinates specialists for:

- IBKR API capability detection, account snapshots, market-data entitlement probes, order previews, and gated live order routing.
- Portfolio construction, rebalancing, and ROI-oriented allocation across daily, short, medium, and long horizons.
- Quantitative research, factor analysis, backtesting, and algorithm diagnostics.
- Market, sentiment, politics, macro, regulatory, and paid-research synthesis.
- Risk review, drawdown controls, liquidity checks, leverage limits, and pre-trade verdicts.

Built on [Agency Swarm](https://github.com/VRSEN/agency-swarm).

## Agent Roster

| Agent | Owns |
|---|---|
| **Orchestrator** | Routes work to the right trading specialists. |
| **Trade Execution Agent** | IBKR connection checks, account snapshots, market-data probes, order previews, and safety-gated live orders. |
| **Portfolio Manager** | Allocation, position sizing, rebalancing, and multi-horizon portfolio plans. |
| **Quantitative Analyst** | Backtests, signals, factor analysis, and algorithm research. |
| **Market Research Analyst** | Fundamentals, news, sentiment, politics, macro, regulation, and research-source synthesis. |
| **Risk Manager** | Exposure, drawdown, liquidity, leverage, stops, margin, and pre-trade risk controls. |
| **Data Analyst** | General CSV/Excel analysis, dashboards, charts, KPIs, and broader statistics. |
| **Docs Agent** | Investment memos, research reports, trading journals, policies, SOPs, and formatted exports. |

## Setup

```bash
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

At minimum, configure one model provider key in `.env`, such as `OPENAI_API_KEY`.

For IBKR workflows, start TWS or IB Gateway, enable API access, and configure:

```env
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=19
IBKR_ACCOUNT=
IBKR_READONLY=true
```

Live order submission is blocked unless both are configured:

```env
IBKR_ENABLE_LIVE_TRADING=true
IBKR_TRADE_CONFIRMATION_TOKEN=<your-private-token>
```

## Optional Data Sources

The swarm detects available providers at runtime without exposing secret values:

```env
POLYGON_API_KEY=
ALPHAVANTAGE_API_KEY=
FINNHUB_API_KEY=
FMP_API_KEY=
TIINGO_API_KEY=
NEWSAPI_API_KEY=
SEARCH_API_KEY=
```

## Typical Prompts

- "Check which IBKR and market-data capabilities are currently available."
- "Review my IBKR portfolio and propose risk-adjusted rebalancing actions."
- "Research AAPL using fundamentals, sentiment, politics/regulation, and market context."
- "Backtest a daily momentum strategy on SPY and compare it to buy-and-hold."
- "Risk-check this proposed QQQ trade and preview the IBKR order."
- "Analyze this trading log CSV and turn the findings into an investment memo."

## Risk Notice

This software is a local automation framework. It does not guarantee returns and does not remove trading risk. Use paper trading first, verify all data and orders manually, and comply with your broker, tax, and regulatory obligations.
