"""Market Data MCP Tools — CONCEPT:EX-AHE.harness.ee-7."""

from typing import Any

import json

from emerald_exchange.backends import ExchangeBackend


def register_market_data_tools(mcp: Any, backend: ExchangeBackend) -> None:
    """Register market data tools on the MCP server."""

    @mcp.tool(tags=["market-data"])
    def emerald_market_data(
        action: str,
        symbol: str = "",
        period: str = "1y",
        interval: str = "1d",
    ) -> str:
        """Market data operations. CONCEPT:EX-AHE.harness.ee-7

        Actions:
        - 'quote': Get current quote for a symbol
        - 'historical': Get OHLCV historical data
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
            data = backend.get_historical(symbol, period, interval)
            return json.dumps(
                [
                    {
                        "t": d.timestamp,
                        "o": d.open,
                        "h": d.high,
                        "l": d.low,
                        "c": d.close,
                        "v": d.volume,
                    }
                    for d in data[:50]
                ]
            )
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
