from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from agency_swarm.tools import BaseTool
from pydantic import Field

from .common import bool_env, compact_error, ibkr_settings, package_available


class IBKROrderTool(BaseTool):
    """
    Previews or submits stock orders through Interactive Brokers.

    Defaults to preview mode. Live submission requires IBKR_ENABLE_LIVE_TRADING=true
    and confirmation_token matching IBKR_TRADE_CONFIRMATION_TOKEN.
    """

    symbol: str = Field(..., description="Stock symbol, e.g. AAPL.")
    action: str = Field(..., description="BUY or SELL.")
    quantity: float = Field(..., description="Share quantity.")
    order_type: str = Field(default="MKT", description="MKT, LMT, STP, or STP LMT.")
    limit_price: float | None = Field(default=None, description="Limit price for LMT or STP LMT orders.")
    stop_price: float | None = Field(default=None, description="Stop price for STP or STP LMT orders.")
    time_in_force: str = Field(default="DAY", description="DAY, GTC, IOC, etc.")
    submit: bool = Field(default=False, description="If false, only return an order preview.")
    confirmation_token: str | None = Field(
        default=None,
        description="Required for live submission. Must match IBKR_TRADE_CONFIRMATION_TOKEN.",
    )

    def run(self):
        if not package_available("ib_insync"):
            return json.dumps(
                {
                    "ok": False,
                    "error": "ib_insync is not installed. Install requirements.txt before using IBKR tools.",
                },
                indent=2,
            )
        from ib_insync import IB, LimitOrder, MarketOrder, Stock, StopLimitOrder, StopOrder  # noqa: PLC0415

        action = self.action.upper().strip()
        order_type = self.order_type.upper().strip()
        if action not in {"BUY", "SELL"}:
            return json.dumps({"ok": False, "error": "action must be BUY or SELL"}, indent=2)
        if self.quantity <= 0:
            return json.dumps({"ok": False, "error": "quantity must be positive"}, indent=2)

        settings = ibkr_settings()
        contract = Stock(self.symbol.upper().strip(), "SMART", "USD")
        if order_type == "MKT":
            order = MarketOrder(action, self.quantity, tif=self.time_in_force)
        elif order_type == "LMT":
            if self.limit_price is None:
                return json.dumps({"ok": False, "error": "limit_price is required for LMT orders"}, indent=2)
            order = LimitOrder(action, self.quantity, self.limit_price, tif=self.time_in_force)
        elif order_type == "STP":
            if self.stop_price is None:
                return json.dumps({"ok": False, "error": "stop_price is required for STP orders"}, indent=2)
            order = StopOrder(action, self.quantity, self.stop_price, tif=self.time_in_force)
        elif order_type == "STP LMT":
            if self.limit_price is None or self.stop_price is None:
                return json.dumps(
                    {"ok": False, "error": "limit_price and stop_price are required for STP LMT orders"},
                    indent=2,
                )
            order = StopLimitOrder(action, self.quantity, self.limit_price, self.stop_price, tif=self.time_in_force)
        else:
            return json.dumps({"ok": False, "error": "order_type must be MKT, LMT, STP, or STP LMT"}, indent=2)
        if settings.account:
            order.account = settings.account

        preview = {
            "symbol": contract.symbol,
            "action": action,
            "quantity": self.quantity,
            "order_type": order_type,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force,
            "account": settings.account,
            "submit_requested": self.submit,
            "live_trading_enabled": bool_env("IBKR_ENABLE_LIVE_TRADING", False),
        }
        if not self.submit:
            return json.dumps({"ok": True, "mode": "preview", "order": preview}, indent=2, default=str)
        if not bool_env("IBKR_ENABLE_LIVE_TRADING", False):
            return json.dumps(
                {
                    "ok": False,
                    "mode": "blocked",
                    "reason": "Set IBKR_ENABLE_LIVE_TRADING=true to permit order submission.",
                    "order": preview,
                },
                indent=2,
                default=str,
            )
        expected_token = os.getenv("IBKR_TRADE_CONFIRMATION_TOKEN")
        if not expected_token or self.confirmation_token != expected_token:
            return json.dumps(
                {
                    "ok": False,
                    "mode": "blocked",
                    "reason": "confirmation_token did not match IBKR_TRADE_CONFIRMATION_TOKEN.",
                    "order": preview,
                },
                indent=2,
                default=str,
            )

        ib = IB()
        try:
            ib.connect(settings.host, settings.port, clientId=settings.client_id)
            ib.qualifyContracts(contract)
            trade = ib.placeOrder(contract, order)
            ib.sleep(1)
            return json.dumps(
                {
                    "ok": True,
                    "mode": "submitted",
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "order": preview,
                    "broker_status": trade.orderStatus.status,
                    "order_id": trade.order.orderId,
                },
                indent=2,
                default=str,
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": compact_error(exc), "order": preview}, indent=2, default=str)
        finally:
            if ib.isConnected():
                ib.disconnect()
