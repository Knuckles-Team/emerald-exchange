"""Order Management MCP Tools — CONCEPT:EX-AHE.harness.ee-8.

``submit_exchange_order`` is the one guarded exchange submit: both
``emerald_orders_submit`` and the venue-routed ``emerald_orders_place``
(CONN-EMERALD-EXCHANGE-X402-R015) call it, so ``RiskGuard.pre_trade_check``
applies to every exchange order.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field

from emerald_exchange.backends import ExchangeBackend, OrderSide, OrderType
from emerald_exchange.risk_guards import RiskGuard

if TYPE_CHECKING:
    from emerald_exchange.payments.service import WalletService


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
            return json.dumps(
                submit_exchange_order(
                    backend, risk_guard, symbol, side, qty, order_type, limit_price
                )
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


def register_unified_order_tools(
    mcp: Any, backend: ExchangeBackend, risk_guard: RiskGuard, wallet: WalletService
) -> None:
    """One order surface across the exchange venue and the wallet rail (X402-R015)."""
    from emerald_exchange.payments.governor import parse_amount
    from emerald_exchange.payments.ledger import OrderRecord
    from emerald_exchange.payments.refusals import PaymentRefused

    ledger = wallet.ledger

    @mcp.tool(
        name="emerald_orders_place",
        tags={"orders"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def emerald_orders_place(
        venue: Literal["exchange", "wallet"],
        side: Literal["buy", "sell", "send"],
        asset: Annotated[
            str,
            Field(
                description="exchange: market symbol such as BTC/USD; "
                "wallet: token contract address or 'native'"
            ),
        ],
        amount: Annotated[str, Field(description="Decimal quantity in asset units")],
        request_id: Annotated[str, Field(description="Caller idempotency key")],
        order_type: Literal["market", "limit"] = "market",
        limit_price: float = 0.0,
        network: Annotated[str, Field(description="wallet: runtime network name")] = "",
        to: Annotated[str, Field(description="wallet: recipient address")] = "",
    ) -> dict[str, Any]:
        """Place one order: buy or sell on the exchange venue, send on the wallet rail."""
        try:
            if venue == "wallet":
                if side != "send":
                    raise PaymentRefused(
                        "ORDER_SIDE_UNSUPPORTED", venue=venue, side=side
                    )
                token = "" if asset.strip().lower() == "native" else asset
                if token:
                    return wallet.transfer_token(network, token, to, amount, request_id)
                return wallet.transfer_native(network, to, amount, request_id)
            if venue != "exchange":
                raise PaymentRefused("ORDER_VENUE_UNKNOWN", venue=venue)
            if side not in ("buy", "sell"):
                raise PaymentRefused("ORDER_SIDE_UNSUPPORTED", venue=venue, side=side)
            if not request_id or not request_id.strip():
                raise PaymentRefused("PAYMENTS_REQUEST_ID_REQUIRED")
            existing = ledger.find(request_id.strip())
            if existing is not None:
                return {**existing, "replayed": True}
            qty = parse_amount(amount)
            result = submit_exchange_order(
                backend, risk_guard, asset, side, float(qty), order_type, limit_price
            )
            if "error" in result:
                return result
            record = ledger.append(
                OrderRecord(
                    venue="exchange",
                    order_id=str(result["order_id"]),
                    side=side,
                    asset=asset,
                    amount=format(qty, "f"),
                    status=str(result["status"]).lower(),
                    mode=str(backend.mode),
                    request_id=request_id.strip(),
                    reference=str(result.get("exchange") or ""),
                    kind="order",
                )
            )
            return {**record.as_dict(), "replayed": False, "exchange_result": result}
        except PaymentRefused as refusal:
            return refusal.as_result()

    @mcp.tool(
        name="emerald_orders_list",
        tags={"orders"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def emerald_orders_list(
        venue: Literal["all", "exchange", "wallet"] = "all", limit: int = 50
    ) -> dict[str, Any]:
        """Orders and wallet sends from the one ledger, newest first."""
        return {"orders": ledger.records(venue, min(max(int(limit), 1), 500))}
