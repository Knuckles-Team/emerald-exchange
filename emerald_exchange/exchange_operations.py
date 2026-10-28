"""The exchange operations served as per-operation MCP tools: reads only.

Placing, modifying or cancelling orders (and connect/disconnect) changes
exchange state, so those go only through the risk-guarded
``emerald_orders_*`` tools (``mcp/mcp_orders.py``), which check RiskGuard
limits, halts and live-mode approval first. Serving the backend class
directly would have exposed ``submit_order``/``cancel_order`` as unguarded
per-operation tools, a way around the guard.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from emerald_exchange.backends import (
    BACKEND_REGISTRY,
    OHLCV,
    AccountInfo,
    ExchangeBackend,
    ExecutionResult,
    Position,
    Quote,
)

#: Backend methods that may be served without the risk guard.
READ_OPERATIONS = (
    "get_quote",
    "get_historical",
    "get_positions",
    "get_account",
    "get_account_snapshot",
    "get_order_status",
    "exchanges",
)


class ExchangeReadOperations:
    """Read-only exchange operations over the configured backend."""

    def __init__(self, backend: ExchangeBackend) -> None:
        self._backend = backend

    def get_quote(self, symbol: str) -> Quote:
        """Latest quote for one symbol."""
        return self._backend.get_quote(symbol)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        """Historical OHLCV bars for one symbol."""
        return self._backend.get_historical(symbol, period=period, interval=interval)

    def get_positions(self) -> list[Position]:
        """Open positions."""
        return self._backend.get_positions()

    def get_account(self) -> AccountInfo:
        """Account balances and buying power."""
        return self._backend.get_account()

    def get_account_snapshot(self) -> list[dict[str, Any]]:
        """Read one Alpaca account and its positions as an ingestible record."""
        if self._backend.name != "alpaca":
            raise ValueError("account snapshot source requires the Alpaca backend")
        account = self._backend.get_account()
        if not account.account_id:
            raise ValueError("account snapshot source requires an account identity")
        positions = self._backend.get_positions()
        return [{**asdict(account), "positions": [asdict(item) for item in positions]}]

    def exchanges(self) -> dict[str, Any]:
        """Available exchange backends, the active backend and its mode."""
        return {
            "available": list(BACKEND_REGISTRY),
            "active": self._backend.name,
            "mode": self._backend.mode,
        }

    def get_order_status(self, order_id: str) -> ExecutionResult:
        """Status of one submitted order."""
        return self._backend.get_order_status(order_id)
