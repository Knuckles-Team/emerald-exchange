"""Market Data MCP Tools — CONCEPT:EX-AHE.harness.ee-7."""

import json
from typing import Any

from emerald_exchange.backends import (
    OHLCV,
    ExchangeBackend,
    HistoricalDataError,
    UnsupportedIntervalError,
)

#: Default and maximum page size for the 'historical' action. A caller that
#: wants everything pages through with `offset`, rather than the response
#: silently discarding bars past a fixed cutoff.
DEFAULT_HISTORICAL_LIMIT = 500
MAX_HISTORICAL_LIMIT = 5000


def _bar(d: OHLCV) -> dict[str, Any]:
    return {
        "t": d.timestamp,
        "o": d.open,
        "h": d.high,
        "l": d.low,
        "c": d.close,
        "v": d.volume,
    }


def _paginate_historical(data: list[OHLCV], offset: int, limit: int) -> dict[str, Any]:
    """Page ``data`` explicitly: every bar is reachable, none is silently dropped."""
    offset = max(0, offset)
    limit = max(1, min(limit, MAX_HISTORICAL_LIMIT))
    page = data[offset : offset + limit]
    return {
        "bars": [_bar(d) for d in page],
        "total": len(data),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(data),
    }


def register_market_data_tools(mcp: Any, backend: ExchangeBackend) -> None:
    """Register market data tools on the MCP server."""

    @mcp.tool(tags=["market-data"])
    def emerald_market_data(
        action: str,
        symbol: str = "",
        period: str = "1y",
        interval: str = "1d",
        offset: int = 0,
        limit: int = DEFAULT_HISTORICAL_LIMIT,
    ) -> str:
        """Market data operations. CONCEPT:EX-AHE.harness.ee-7

        Actions:
        - 'quote': Get current quote for a symbol
        - 'historical': Get OHLCV historical data, paginated via `offset`/`limit`
          (see the response's `total`/`has_more` to walk the full history —
          nothing beyond one page is ever silently dropped). An `interval` the
          backend does not support, or a data-fetch failure, is returned as an
          explicit `error`/`error_type`, never as a silent substitution.
        - 'exchanges': List available exchange backends
        """
        if action == "quote":
            if not symbol:
                return json.dumps({"error": "symbol required"})
            q = backend.get_quote(symbol)
            return json.dumps(
                {
                    "symbol": q.symbol,
                    "bid": q.bid,
                    "ask": q.ask,
                    "last": q.last,
                    "volume": q.volume,
                }
            )
        elif action == "historical":
            if not symbol:
                return json.dumps({"error": "symbol required"})
            try:
                data = backend.get_historical(symbol, period, interval)
            except UnsupportedIntervalError as exc:
                return json.dumps(
                    {"error": str(exc), "error_type": "unsupported_interval"}
                )
            except HistoricalDataError as exc:
                return json.dumps(
                    {"error": str(exc), "error_type": "historical_data_error"}
                )
            return json.dumps(_paginate_historical(data, offset, limit))
        elif action == "exchanges":
            from emerald_exchange.backends import BACKEND_REGISTRY

            return json.dumps(
                {
                    "available": list(BACKEND_REGISTRY.keys()),
                    "active": backend.name,
                    "mode": backend.mode,
                }
            )
        return json.dumps({"error": f"Unknown action: {action}"})
