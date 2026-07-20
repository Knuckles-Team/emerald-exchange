"""Native epistemic-graph ingestion for Emerald Exchange records (typed graph nodes).

CONCEPT:AU-KG.ingest.enterprise-source-extractor. The connector natively pushes its live
trading data into the ONE epistemic-graph knowledge graph as **typed OWL nodes** —
:Instrument, :Portfolio, :Position, :Trade, :Quote, :MarketBar (OHLCV timeseries) — plus
their links (:ofInstrument / :holdsPosition / :tradesInstrument / :settledInPortfolio)
through the required ``agent_utilities.knowledge_graph.memory.native_ingest`` authority.
Node ids follow ``emerald:<class>:<externalId>`` and every ``node_type`` matches a class
federated by ``emerald_exchange.ontology`` (emerald.ttl / quant.ttl).
"""

from __future__ import annotations

import logging
from typing import Any

from agent_utilities.knowledge_graph.memory.native_ingest import (
    ingest_documents as _native_ingest_documents,
)
from agent_utilities.knowledge_graph.memory.native_ingest import (
    ingest_entities as _native_ingest_entities,
)

logger = logging.getLogger("emerald_exchange.kg")

_SOURCE = "emerald-exchange"
_DOMAIN = "emerald"


def ingest_entities(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
    *,
    source: str = _SOURCE,
    domain: str = _DOMAIN,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int]:
    """Write canonical typed nodes and relationships through native ingestion."""
    return _native_ingest_entities(
        entities,
        relationships,
        source=source,
        domain=domain,
        client=client,
        graph=graph,
    )


def ingest_documents(
    documents: list[dict[str, Any]],
    *,
    source: str = _SOURCE,
    domain: str = _DOMAIN,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int]:
    """Write text records as ``:Document`` nodes for semantic search."""
    return _native_ingest_documents(
        documents, source=source, domain=domain, client=client, graph=graph
    )


# --------------------------------------------------------------------------- #
# Record mappers — records → typed entity/relationship dicts.
# --------------------------------------------------------------------------- #
def _portfolio_id(exchange: str) -> str:
    return f"emerald:portfolio:{exchange or 'unknown'}"


def _instrument_id(symbol: str) -> str:
    return f"emerald:instrument:{symbol}"


def map_account(account: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Map an AccountInfo-shaped dict → a :Portfolio node."""
    exchange = account.get("exchange") or "unknown"
    pid = _portfolio_id(exchange)
    node = {
        "id": pid,
        "node_type": "Portfolio",
        "name": f"{exchange} portfolio",
        "exchange": exchange,
        "equity": account.get("equity"),
        "cash": account.get("cash"),
        "buyingPower": account.get("buying_power"),
        "marginUsed": account.get("margin_used"),
        "currency": account.get("currency"),
        "externalToolId": exchange,
    }
    return [node], []


def map_positions(
    positions: list[dict[str, Any]],
) -> tuple[list[dict], list[dict]]:
    """Map Position-shaped dicts → :Position (+ :Instrument) nodes and their links."""
    entities: list[dict] = []
    rels: list[dict] = []
    for pos in positions or []:
        symbol = pos.get("symbol")
        if not symbol:
            continue
        exchange = pos.get("exchange") or "unknown"
        pos_id = f"emerald:position:{exchange}:{symbol}"
        inst_id = _instrument_id(symbol)
        entities.append(
            {
                "id": pos_id,
                "node_type": "Position",
                "name": f"{symbol} @ {exchange}",
                "exchange": exchange,
                "qty": pos.get("qty"),
                "avgEntryPrice": pos.get("avg_entry_price"),
                "currentPrice": pos.get("current_price"),
                "unrealizedPnl": pos.get("unrealized_pnl"),
                "side": pos.get("side"),
                "externalToolId": f"{exchange}:{symbol}",
            }
        )
        entities.append(
            {
                "id": inst_id,
                "node_type": "Instrument",
                "name": symbol,
                "symbol": symbol,
            }
        )
        rels.append(
            {"source": pos_id, "target": inst_id, "relationship": "ofInstrument"}
        )
        rels.append(
            {
                "source": _portfolio_id(exchange),
                "target": pos_id,
                "relationship": "holdsPosition",
            }
        )
    return entities, rels


def map_quote(quote: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Map a Quote-shaped dict → :Quote (+ :Instrument) nodes and their link."""
    symbol = quote.get("symbol")
    if not symbol:
        return [], []
    inst_id = _instrument_id(symbol)
    ts = quote.get("timestamp") or ""
    q_id = f"emerald:quote:{symbol}:{ts}" if ts else f"emerald:quote:{symbol}:latest"
    entities = [
        {
            "id": inst_id,
            "node_type": "Instrument",
            "name": symbol,
            "symbol": symbol,
        },
        {
            "id": q_id,
            "node_type": "Quote",
            "name": f"{symbol} quote",
            "symbol": symbol,
            "bid": quote.get("bid"),
            "ask": quote.get("ask"),
            "last": quote.get("last"),
            "volume": quote.get("volume"),
            "barTimestamp": ts or None,
        },
    ]
    rels = [{"source": q_id, "target": inst_id, "relationship": "ofInstrument"}]
    return entities, rels


def map_bars(symbol: str, bars: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Map OHLCV-shaped dicts → :MarketBar timeseries (+ :Instrument) nodes and links."""
    if not symbol:
        return [], []
    inst_id = _instrument_id(symbol)
    entities: list[dict] = [
        {"id": inst_id, "node_type": "Instrument", "name": symbol, "symbol": symbol}
    ]
    rels: list[dict] = []
    for bar in bars or []:
        ts = bar.get("timestamp") or bar.get("t")
        if not ts:
            continue
        bar_id = f"emerald:bar:{symbol}:{ts}"
        entities.append(
            {
                "id": bar_id,
                "node_type": "MarketBar",
                "name": f"{symbol} {ts}",
                "symbol": symbol,
                "barTimestamp": ts,
                "open": bar.get("open", bar.get("o")),
                "high": bar.get("high", bar.get("h")),
                "low": bar.get("low", bar.get("l")),
                "close": bar.get("close", bar.get("c")),
                "volume": bar.get("volume", bar.get("v")),
            }
        )
        rels.append(
            {"source": bar_id, "target": inst_id, "relationship": "ofInstrument"}
        )
    return entities, rels


def map_trade(trade: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Map an ExecutionResult-shaped dict → a :Trade node (+ links) if it has an id."""
    oid = trade.get("order_id")
    if not oid:
        return [], []
    exchange = trade.get("exchange") or "unknown"
    symbol = trade.get("symbol")
    t_id = f"emerald:trade:{oid}"
    node = {
        "id": t_id,
        "node_type": "Trade",
        "name": f"trade {oid}",
        "exchange": exchange,
        "orderStatus": trade.get("status"),
        "filledQty": trade.get("filled_qty"),
        "averagePrice": trade.get("average_price"),
        "fees": trade.get("fees"),
        "side": trade.get("side"),
        "barTimestamp": trade.get("timestamp") or None,
        "externalToolId": str(oid),
    }
    entities = [node]
    rels = [
        {
            "source": t_id,
            "target": _portfolio_id(exchange),
            "relationship": "settledInPortfolio",
        }
    ]
    if symbol:
        inst_id = _instrument_id(symbol)
        node["symbol"] = symbol
        entities.append(
            {
                "id": inst_id,
                "node_type": "Instrument",
                "name": symbol,
                "symbol": symbol,
            }
        )
        rels.append(
            {
                "source": t_id,
                "target": inst_id,
                "relationship": "tradesInstrument",
            }
        )
    return entities, rels


# --------------------------------------------------------------------------- #
# High-level: pull a live snapshot off a backend and push it into the KG.
# --------------------------------------------------------------------------- #
def ingest_backend_snapshot(
    backend: Any,
    symbols: list[str] | None = None,
    *,
    include_history: bool = False,
    period: str = "1mo",
    interval: str = "1d",
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int]:
    """List account + positions (+ optional quotes/bars for ``symbols``) off a live
    ExchangeBackend and push them into the KG as canonical typed nodes.
    """
    entities: list[dict] = []
    rels: list[dict] = []

    try:
        acct = backend.get_account()
        e, r = map_account(_as_dict(acct))
        entities += e
        rels += r
    except Exception as e:  # noqa: BLE001
        logger.debug("Operation failed: error_type=%s", type(e).__name__)

    try:
        positions = [_as_dict(p) for p in backend.get_positions()]
        e, r = map_positions(positions)
        entities += e
        rels += r
    except Exception as e:  # noqa: BLE001
        logger.debug("Operation failed: error_type=%s", type(e).__name__)

    for sym in symbols or []:
        try:
            e, r = map_quote(_as_dict(backend.get_quote(sym)))
            entities += e
            rels += r
        except Exception as e:  # noqa: BLE001
            logger.debug("Operation failed: error_type=%s", type(e).__name__)
        if include_history:
            try:
                bars = [
                    _as_dict(b) for b in backend.get_historical(sym, period, interval)
                ]
                e, r = map_bars(sym, bars)
                entities += e
                rels += r
            except Exception as e:  # noqa: BLE001
                logger.debug("Operation failed: error_type=%s", type(e).__name__)

    return ingest_entities(entities, rels, client=client, graph=graph)


def _as_dict(obj: Any) -> dict[str, Any]:
    """Coerce a dataclass/record/dict into a plain dict of its public fields."""
    if isinstance(obj, dict):
        return obj
    import dataclasses

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return {
        k: getattr(obj, k)
        for k in dir(obj)
        if not k.startswith("_") and not callable(getattr(obj, k, None))
    }
