from __future__ import annotations

import json
from datetime import datetime, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field

from .common import compact_error, ibkr_settings, package_available


class IBKRAccountSnapshot(BaseTool):
    """
    Connects to Interactive Brokers TWS/IB Gateway and returns accounts, positions,
    balances, open orders, and optional market-data entitlement probes.
    """

    include_positions: bool = Field(default=True, description="Include current positions.")
    include_open_orders: bool = Field(default=True, description="Include open orders.")
    market_data_probe_symbols: list[str] = Field(
        default=[],
        description="Optional stock symbols to probe with IBKR market data, e.g. ['SPY', 'AAPL'].",
    )
    timeout_seconds: float = Field(default=10.0, description="Connection and market-data timeout in seconds.")

    def run(self):
        if not package_available("ib_insync"):
            return json.dumps(
                {
                    "ok": False,
                    "error": "ib_insync is not installed. Install requirements.txt before using IBKR tools.",
                },
                indent=2,
            )

        from ib_insync import IB, Stock  # noqa: PLC0415

        settings = ibkr_settings()
        ib = IB()
        try:
            ib.connect(settings.host, settings.port, clientId=settings.client_id, timeout=self.timeout_seconds)
            accounts = ib.managedAccounts()
            account_values = [
                {
                    "account": value.account,
                    "tag": value.tag,
                    "value": value.value,
                    "currency": value.currency,
                    "model_code": value.modelCode,
                }
                for value in ib.accountSummary(account=settings.account or "")
            ]
            positions = []
            if self.include_positions:
                positions = [
                    {
                        "account": pos.account,
                        "symbol": pos.contract.symbol,
                        "sec_type": pos.contract.secType,
                        "exchange": pos.contract.exchange,
                        "currency": pos.contract.currency,
                        "position": pos.position,
                        "avg_cost": pos.avgCost,
                    }
                    for pos in ib.positions()
                ]
            open_orders = []
            if self.include_open_orders:
                open_orders = [
                    {
                        "order_id": trade.order.orderId,
                        "action": trade.order.action,
                        "quantity": trade.order.totalQuantity,
                        "order_type": trade.order.orderType,
                        "limit_price": trade.order.lmtPrice,
                        "status": trade.orderStatus.status,
                        "symbol": trade.contract.symbol,
                    }
                    for trade in ib.openTrades()
                ]
            probes = []
            for symbol in self.market_data_probe_symbols:
                contract = Stock(symbol.upper(), "SMART", "USD")
                ib.qualifyContracts(contract)
                ticker = ib.reqMktData(contract, "", False, False)
                ib.sleep(min(2.0, self.timeout_seconds))
                probes.append(
                    {
                        "symbol": symbol.upper(),
                        "last": ticker.last,
                        "bid": ticker.bid,
                        "ask": ticker.ask,
                        "close": ticker.close,
                        "market_price": ticker.marketPrice(),
                        "has_live_or_delayed_data": any(
                            value is not None and value == value
                            for value in (ticker.last, ticker.bid, ticker.ask, ticker.close)
                        ),
                    }
                )
                ib.cancelMktData(contract)
            return json.dumps(
                {
                    "ok": True,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "host": settings.host,
                    "port": settings.port,
                    "accounts": accounts,
                    "selected_account": settings.account,
                    "account_values": account_values,
                    "positions": positions,
                    "open_orders": open_orders,
                    "market_data_probes": probes,
                },
                indent=2,
                default=str,
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": compact_error(exc)}, indent=2)
        finally:
            if ib.isConnected():
                ib.disconnect()
