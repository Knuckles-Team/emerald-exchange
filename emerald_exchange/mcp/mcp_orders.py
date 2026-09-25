"""Order Management MCP Tools — CONCEPT:EX-AHE.harness.ee-8."""

import hashlib
import json
import re
import threading

from typing import Any, Literal
from pydantic import Field

from emerald_exchange.backends import ExchangeBackend, OrderSide, OrderType, TradingMode
from emerald_exchange.risk_guards import RiskGuard
from emerald_exchange.trading.governed import LIVE_ORDER_GUIDANCE


def _approval_required(action: str) -> str:
    return json.dumps(
        {"status": "approval_required", "action": action, "how": LIVE_ORDER_GUIDANCE}
    )


def register_order_tools(
    mcp: Any, backend: ExchangeBackend, risk_guard: RiskGuard
) -> None:
    """Register order management tools. All orders go through risk guard.

    ``backend`` is the :class:`~emerald_exchange.trading.GovernedBackend`: in
    paper mode (the default) orders fill on the paper account; in live mode
    ``submit``/``cancel`` answer ``approval_required`` -- a live order is
    placed only by ``emerald_live_orders(action='execute_approved')``.
    """
    paper_lock = threading.Lock()
    paper_receipts: dict[str, tuple[str, str]] = {}

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
        - 'submit': Submit a PAPER order (goes through risk guard); in live
          mode this answers ``approval_required`` and places nothing
        - 'cancel': Cancel a paper order (``approval_required`` in live mode)
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

        if action in ("submit", "cancel") and backend.mode == TradingMode.LIVE:
            return _approval_required(action)

        if action == "submit":
            if not symbol or qty <= 0:
                return json.dumps({"error": "symbol and qty > 0 required"})

            # Pre-trade risk check
            acct = backend.get_account()
            price = limit_price if limit_price > 0 else backend.get_quote(symbol).last
            if price <= 0:
                return json.dumps({"error": "a usable quote is required"})

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

    @mcp.tool(tags=["orders", "paper"])
    def emerald_paper_orders(
        action: Literal["submit"],
        request_id: str,
        symbol: str = "",
        side: Literal["buy", "sell"] = "buy",
        qty: float = 0.0,
        order_type: Literal["market", "limit", "stop", "stop_limit"] = "market",
        limit_price: float = 0.0,
    ) -> str:
        """Paper-only order seam for GraphOS's durable request fence.

        This local fence handles concurrent and repeated calls in one process.
        GraphOS owns durable at-most-once admission across connector restarts.
        """
        if backend.mode is not TradingMode.PAPER:
            return json.dumps(
                {"status": "refused", "error": "paper mode is unavailable"}
            )
        if not re.fullmatch(r"[A-Za-z0-9:._-]{8,128}", request_id):
            return json.dumps({"status": "refused", "error": "invalid request id"})
        if action != "submit":
            return json.dumps(
                {"status": "refused", "error": "paper action is unavailable"}
            )
        payload = [action, symbol, side, qty, order_type, limit_price]
        digest = hashlib.sha256(
            json.dumps(payload, separators=(",", ":")).encode()
        ).hexdigest()
        with paper_lock:
            previous = paper_receipts.get(request_id)
            if previous is not None:
                if previous[0] != digest:
                    return json.dumps(
                        {"status": "refused", "error": "request id conflict"}
                    )
                return previous[1]
            if len(paper_receipts) >= 100_000:
                return json.dumps(
                    {"status": "refused", "error": "paper request fence is full"}
                )
            paper_receipts[request_id] = (
                digest,
                json.dumps({"status": "indeterminate"}),
            )
            try:
                result = emerald_orders(
                    action=action,
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    order_type=order_type,
                    limit_price=limit_price,
                )
            except Exception:
                return paper_receipts[request_id][1]
            paper_receipts[request_id] = (digest, result)
            return result
