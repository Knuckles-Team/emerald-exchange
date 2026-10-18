"""The exchange operations served as per-operation MCP tools: reads only.

Placing, modifying or cancelling orders (and connect/disconnect) changes
exchange state, so those go only through the risk-guarded
``emerald_orders_*`` tools (``mcp/mcp_orders.py``), which check RiskGuard
limits, halts and live-mode approval first. Serving the backend class
directly would have exposed ``submit_order``/``cancel_order`` as unguarded
per-operation tools, a way around the guard.
"""

from __future__ import annotations

from emerald_exchange.backends import (
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
    "get_order_status",
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

    def get_order_status(self, order_id: str) -> ExecutionResult:
        """Status of one submitted order."""
        return self._backend.get_order_status(order_id)
