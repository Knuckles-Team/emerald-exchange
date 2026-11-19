"""Order Management MCP Tools — CONCEPT:EX-AHE.harness.ee-8.

One typed tool per order operation. ``submit_exchange_order`` is the one
guarded exchange submit, so ``RiskGuard.pre_trade_check`` applies to every
exchange order. Submit, cancel and halt are destructive: each asks the caller
to confirm (or takes ``confirm=true``) before it acts.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastmcp import Context
from pydantic import Field

from emerald_exchange.backends import ExchangeBackend, OrderSide, OrderType
from emerald_exchange.mcp._hints import (
    DESTRUCTIVE,
    READ,
    WRITE,
    refused_unless_confirmed,
)
from emerald_exchange.risk_guards import RiskGuard

Confirm = Annotated[
    bool,
    Field(description="Confirm this destructive call when the client cannot be asked"),
]


def submit_exchange_order(
    backend: ExchangeBackend,
    risk_guard: RiskGuard,
    symbol: str,
    side: str,
    qty: float,
    order_type: str = "market",
    limit_price: float = 0.0,
) -> dict[str, Any]:
    """Pre-trade risk check, then submit on the configured exchange backend."""
    if not symbol or qty <= 0:
        return {"error": "symbol and qty > 0 required"}

    acct = backend.get_account()
    price = limit_price if limit_price > 0 else backend.get_quote(symbol).last
    if price <= 0:
        price = 100.0  # Fallback for paper

    is_live = backend.mode == "live"
    check = risk_guard.pre_trade_check(
        symbol, qty, price, acct.equity, acct.cash, is_live
    )
    if not check.approved:
        return {
            "error": check.reason,
            "approved": False,
            "risk_score": check.risk_score,
        }

    # Use adjusted qty if risk guard sized it down
    final_qty = check.adjusted_qty if check.adjusted_qty > 0 else qty
    result = backend.submit_order(
        symbol,
        OrderSide(side),
        final_qty,
        OrderType(order_type),
        limit_price if limit_price > 0 else None,
    )
    return {
        "order_id": result.order_id,
        "status": result.status,
        "filled_qty": result.filled_qty,
        "avg_price": result.average_price,
        "fees": result.fees,
        "exchange": result.exchange,
        "risk_check": check.reason,
        "risk_score": check.risk_score,
    }


def register_order_tools(
    mcp: Any, backend: ExchangeBackend, risk_guard: RiskGuard
) -> None:
    """Register order management tools. All orders go through risk guard."""

    @mcp.tool(tags={"orders"}, annotations=DESTRUCTIVE)
    async def emerald_orders_submit(
        symbol: Annotated[str, Field(description="Market symbol, for example AAPL")],
        qty: Annotated[float, Field(description="Quantity; must be above zero")],
        side: Literal["buy", "sell"] = "buy",
        order_type: Literal["market", "limit", "stop", "stop_limit"] = "market",
        limit_price: Annotated[
            float, Field(description="Limit price; 0 for a market order")
        ] = 0.0,
        confirm: Confirm = False,
        ctx: Context | None = None,
    ) -> Any:
        """Submit an order after the pre-trade risk check. CONCEPT:EX-AHE.harness.ee-8"""
        refused = await refused_unless_confirmed(
            ctx,
            "emerald_orders_submit",
            {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "order_type": order_type,
                "limit_price": limit_price,
            },
            confirm,
        )
        if refused is not None:
            return refused
        return json.dumps(
            submit_exchange_order(
                backend, risk_guard, symbol, side, qty, order_type, limit_price
            )
        )

    @mcp.tool(tags={"orders"}, annotations=DESTRUCTIVE)
    async def emerald_orders_cancel(
        order_id: Annotated[str, Field(description="Exchange order id")],
        confirm: Confirm = False,
        ctx: Context | None = None,
    ) -> Any:
        """Cancel an open order. CONCEPT:EX-AHE.harness.ee-8"""
        if not order_id:
            return json.dumps({"error": "order_id required"})
        refused = await refused_unless_confirmed(
            ctx, "emerald_orders_cancel", {"order_id": order_id}, confirm
        )
        if refused is not None:
            return refused
        ok = backend.cancel_order(order_id)
        return json.dumps({"order_id": order_id, "cancelled": ok})

    @mcp.tool(tags={"orders"}, annotations=READ)
    def emerald_orders_status(
        order_id: Annotated[str, Field(description="Exchange order id")],
    ) -> str:
        """Status, filled quantity and average price of one order. CONCEPT:EX-AHE.harness.ee-8"""
        if not order_id:
            return json.dumps({"error": "order_id required"})
        result = backend.get_order_status(order_id)
        return json.dumps(
            {
                "order_id": result.order_id,
                "status": result.status,
                "filled_qty": result.filled_qty,
                "avg_price": result.average_price,
            }
        )

    @mcp.tool(tags={"orders"}, annotations=DESTRUCTIVE)
    async def emerald_orders_halt(
        confirm: Confirm = False,
        ctx: Context | None = None,
    ) -> Any:
        """Emergency kill switch: halt ALL trading. CONCEPT:EX-AHE.harness.ee-8"""
        refused = await refused_unless_confirmed(
            ctx, "emerald_orders_halt", {}, confirm
        )
        if refused is not None:
            return refused
        risk_guard.halt("Manual kill switch via MCP")
        return json.dumps({"status": "HALTED", "message": "All trading halted"})

    @mcp.tool(tags={"orders"}, annotations=WRITE)
    def emerald_orders_resume() -> str:
        """Resume trading after a halt. CONCEPT:EX-AHE.harness.ee-8"""
        risk_guard.resume()
        return json.dumps({"status": "RESUMED"})
