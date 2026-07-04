"""Order Management MCP Tools — CONCEPT:EX-AHE.harness.ee-8."""

from typing import Any
from pydantic import Field

import json


from emerald_exchange.backends import ExchangeBackend, OrderSide, OrderType
from emerald_exchange.risk_guards import RiskGuard


def register_order_tools(
    mcp: Any, backend: ExchangeBackend, risk_guard: RiskGuard
) -> None:
    """Register order management tools. All orders go through risk guard."""

    @mcp.tool(tags=["orders"])
    def emerald_orders(
        action: str,
        symbol: str = "",
        side: str = Field(default="buy", description="buy or sell"),
        qty: float = 0.0,
        order_type: str = "market",
        limit_price: float = 0.0,
        order_id: str = "",
    ) -> str:
        """Order management with pre-trade risk validation. CONCEPT:EX-AHE.harness.ee-8

        Actions:
        - 'submit': Submit an order (goes through risk guard)
        - 'cancel': Cancel an existing order
        - 'status': Get order status
        - 'halt': Emergency kill switch — halts ALL trading
        - 'resume': Resume trading after halt
        """
        if action == "halt":
            risk_guard.halt("Manual kill switch via MCP")
            return json.dumps({"status": "HALTED", "message": "All trading halted"})

        if action == "resume":
            risk_guard.resume()
            return json.dumps({"status": "RESUMED"})

        if action == "submit":
            if not symbol or qty <= 0:
                return json.dumps({"error": "symbol and qty > 0 required"})

            # Pre-trade risk check
            acct = backend.get_account()
            price = limit_price if limit_price > 0 else backend.get_quote(symbol).last
            if price <= 0:
                price = 100.0  # Fallback for paper

            is_live = backend.mode == "live"
            check = risk_guard.pre_trade_check(
                symbol, qty, price, acct.equity, acct.cash, is_live
            )
            if not check.approved:
                return json.dumps(
                    {
                        "error": check.reason,
                        "approved": False,
                        "risk_score": check.risk_score,
                    }
                )

            # Use adjusted qty if risk guard sized it down
            final_qty = check.adjusted_qty if check.adjusted_qty > 0 else qty
            result = backend.submit_order(
                symbol,
                OrderSide(side),
                final_qty,
                OrderType(order_type),
                limit_price if limit_price > 0 else None,
            )
            return json.dumps(
                {
                    "order_id": result.order_id,
                    "status": result.status,
                    "filled_qty": result.filled_qty,
                    "avg_price": result.average_price,
                    "fees": result.fees,
                    "exchange": result.exchange,
                    "risk_check": check.reason,
                    "risk_score": check.risk_score,
                }
            )

        elif action == "cancel":
            if not order_id:
                return json.dumps({"error": "order_id required"})
            ok = backend.cancel_order(order_id)
            return json.dumps({"order_id": order_id, "cancelled": ok})

        elif action == "status":
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

        return json.dumps({"error": f"Unknown action: {action}"})
