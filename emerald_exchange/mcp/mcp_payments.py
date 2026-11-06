"""Wallet payments: one typed MCP tool per bounded runtime operation.

CONN-EMERALD-EXCHANGE-X402-R008.1. No tool takes ``action`` or untyped
params. Every write passes the governor of R010.1 before the runtime and is
idempotent on ``request_id``. Raw broadcast, the unbounded x402 runtime
call, admin, policy, backup and approval-decision commands are not served.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from pydantic import Field

from emerald_exchange.payments.refusals import PaymentRefused
from emerald_exchange.payments.service import WalletService

READ = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
WRITE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

Network = Annotated[
    str, Field(description="Runtime network name, for example bsc or eth")
]
Address = Annotated[str, Field(description="0x-prefixed EVM address")]
Amount = Annotated[
    str, Field(description="Decimal amount in token units, for example '1.5'")
]
RequestId = Annotated[
    str,
    Field(
        description="Caller idempotency key; a reused key returns the recorded entry"
    ),
]


def _guarded(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except PaymentRefused as refusal:
        return refusal.as_result()


def register_payments_tools(mcp: Any, service: WalletService) -> None:
    """Register the wallet tools on ``mcp``."""

    @mcp.tool(name="emerald_payments_get_wallet", tags={"payments"}, annotations=READ)
    def emerald_payments_get_wallet() -> dict[str, Any]:
        """Public wallet profile: address, chain and policy summary. Holds no key."""
        return _guarded(service.get_wallet)

    @mcp.tool(name="emerald_payments_get_balance", tags={"payments"}, annotations=READ)
    def emerald_payments_get_balance(
        network: Network,
        token: Annotated[
            str, Field(description="Token contract; empty for the native asset")
        ] = "",
        rpc_url: Annotated[
            str, Field(description="https RPC override; default from config")
        ] = "",
    ) -> dict[str, Any]:
        """Native or token balance of the wallet address on one network."""
        return _guarded(lambda: service.get_balance(network, token, rpc_url))

    @mcp.tool(
        name="emerald_payments_get_spend_limits", tags={"payments"}, annotations=READ
    )
    def emerald_payments_get_spend_limits() -> dict[str, Any]:
        """The server-side mode, per-asset limits, approval thresholds and breaker."""
        return _guarded(service.get_spend_limits)

    @mcp.tool(
        name="emerald_payments_transfer_native", tags={"payments"}, annotations=WRITE
    )
    def emerald_payments_transfer_native(
        network: Network, to: Address, amount: Amount, request_id: RequestId
    ) -> dict[str, Any]:
        """Send the native asset. Governed; paper by default."""
        return _guarded(
            lambda: service.transfer_native(network, to, amount, request_id)
        )

    @mcp.tool(
        name="emerald_payments_transfer_token", tags={"payments"}, annotations=WRITE
    )
    def emerald_payments_transfer_token(
        network: Network,
        token: Address,
        to: Address,
        amount: Amount,
        request_id: RequestId,
    ) -> dict[str, Any]:
        """Send a token. Governed; paper by default."""
        return _guarded(
            lambda: service.transfer_token(network, token, to, amount, request_id)
        )

    @mcp.tool(
        name="emerald_payments_approve_allowance", tags={"payments"}, annotations=WRITE
    )
    def emerald_payments_approve_allowance(
        network: Network,
        token: Address,
        spender: Address,
        amount: Amount,
        request_id: RequestId,
    ) -> dict[str, Any]:
        """Approve a token allowance; counts against the same limits as a send."""
        return _guarded(
            lambda: service.approve_allowance(
                network, token, spender, amount, request_id
            )
        )

    @mcp.tool(
        name="emerald_payments_pay_machine_payment",
        tags={"payments"},
        annotations=WRITE,
    )
    def emerald_payments_pay_machine_payment(
        url: Annotated[str, Field(description="https machine-payment endpoint")],
        network: Network,
        token: Address,
        amount: Amount,
        request_id: RequestId,
        method: Literal["GET", "POST"] = "GET",
        json_body: Annotated[str, Field(description="JSON request body for POST")] = "",
    ) -> dict[str, Any]:
        """Pay a machine-payment endpoint a fixed charge; the runtime verifies it equals amount."""
        return _guarded(
            lambda: service.pay_machine_payment(
                url, network, token, amount, method, json_body, request_id
            )
        )
