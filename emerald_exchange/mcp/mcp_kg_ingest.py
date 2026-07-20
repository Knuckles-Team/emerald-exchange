"""KG Ingestion MCP Tools — CONCEPT:AU-KG.ingest.enterprise-source-extractor.

Wire-First native ingestion: lists a live snapshot off the active exchange backend
(account, positions, and optionally quotes / OHLCV history for given symbols) and pushes
it into the ONE epistemic-graph knowledge graph as typed :Portfolio / :Position /
:Instrument / :Quote / :MarketBar / :Trade nodes. Best-effort: returns ``{"ingested": null}``
when no engine is reachable.
"""

from typing import Any

import json

from emerald_exchange.backends import ExchangeBackend


def register_kg_ingest_tools(mcp: Any, backend: ExchangeBackend) -> None:
    """Register the native KG-ingestion tool on the MCP server."""

    @mcp.tool(tags=["kg-ingest"])
    def emerald_ingest_snapshot(
        symbols: str = "",
        include_history: bool = False,
        period: str = "1mo",
        interval: str = "1d",
    ) -> str:
        """Ingest a live trading snapshot into epistemic-graph as typed nodes.

        CONCEPT:AU-KG.ingest.enterprise-source-extractor

        - Always pushes the account (:Portfolio) and open positions (:Position + :Instrument).
        - ``symbols``: comma-separated tickers to also snapshot as :Quote nodes.
        - ``include_history``: also pull OHLCV bars (:MarketBar timeseries) per symbol.
        Best-effort: reports ``ingested: null`` when no KG engine is reachable.
        """
        from emerald_exchange.kg_ingest import ingest_backend_snapshot

        syms = [s.strip() for s in symbols.split(",") if s.strip()]
        result = ingest_backend_snapshot(
            backend,
            syms,
            include_history=include_history,
            period=period,
            interval=interval,
        )
        return json.dumps(
            {
                "exchange": backend.name,
                "mode": str(backend.mode),
                "symbols": syms,
                "ingested": result,
            }
        )
