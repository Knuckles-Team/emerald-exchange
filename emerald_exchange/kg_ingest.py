"""Native epistemic-graph ingestion for Emerald Exchange records (typed graph nodes).

CONCEPT:AU-KG.ingest.enterprise-source-extractor. The connector natively pushes its live
trading data into the ONE epistemic-graph knowledge graph as **typed OWL nodes** —
:Instrument, :Portfolio, :Position, :Trade, :Quote, :MarketBar (OHLCV timeseries) — plus
their links (:ofInstrument / :holdsPosition / :tradesInstrument / :settledInPortfolio),
using the lightweight engine client (``GraphComputeEngine()._client`` + ``txn``): the same
fast client the blob ``MediaStore`` uses, NOT the heavy in-process ingestion engine.

Everything is dependency-/engine-guarded. It first tries the shared fleet primitive
``agent_utilities.knowledge_graph.memory.native_ingest``; if that (or a reachable engine)
is absent, it falls back to a self-contained best-effort txn against ``GraphComputeEngine``,
and if THAT is unavailable every entry point **no-ops** (returns ``None``) so the connector
runs with zero KG infrastructure. Node ids follow ``emerald:<class>:<externalId>`` and every
``type`` matches a class federated by ``emerald_exchange.ontology`` (emerald.ttl / quant.ttl).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("emerald_exchange.kg")

_SOURCE = "emerald-exchange"
_DOMAIN = "emerald"
_DEFAULT_GRAPH = "__commons__"


# --------------------------------------------------------------------------- #
# Engine seam — prefer the shared primitive; fall back to a local txn.
# --------------------------------------------------------------------------- #
def _native_client() -> tuple[Any | None, str]:
    """Return ``(engine_client, graph_name)`` or ``(None, "")`` when unavailable."""
    try:
        from agent_utilities.knowledge_graph.core.graph_compute import (
            GraphComputeEngine,
        )
    except Exception as e:  # noqa: BLE001 — KG stack absent
        logger.debug("KG ingest unavailable (import): %s", e)
        return None, ""
    try:
        engine = GraphComputeEngine()
        client = getattr(engine, "_client", None)
        if client is None:
            return None, ""
        return client, (getattr(engine, "graph_name", None) or _DEFAULT_GRAPH)
    except Exception as e:  # noqa: BLE001 — engine unreachable
        logger.debug("KG ingest: engine unreachable: %s", e)
        return None, ""


def _write_nodes(
    client: Any,
    graph: str,
    nodes: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None,
) -> dict[str, int] | None:
    """Stamp provenance, MERGE the nodes in one txn, then add the edges (best-effort)."""
    nodes = [n for n in nodes if n.get("id")]
    if not nodes:
        return None
    try:
        txn = client.txn.begin(graph=graph)
        for node in nodes:
            props = {k: v for k, v in node.items() if k != "id" and v is not None}
            props.setdefault("source", _SOURCE)
            props.setdefault("domain", _DOMAIN)
            client.txn.add_node(txn, node["id"], props)
        committed = client.txn.commit(txn)
    except Exception as e:  # noqa: BLE001 — engine/txn failure is non-fatal
        logger.warning("KG ingest: txn failed: %s", e)
        return None
    if not committed:
        logger.warning("KG ingest: txn not committed (conflict)")
        return None

    edges = 0
    for rel in relationships or []:
        try:
            client.edges.add(
                rel["source"], rel["target"], {"type": rel.get("type", "RELATED")}
            )
            edges += 1
        except Exception as e:  # noqa: BLE001 — pure edge link, best-effort
            logger.debug("KG ingest: edge skipped: %s", e)

    logger.info("KG ingest[emerald]: wrote %d nodes, %d edges", len(nodes), edges)
    return {"nodes": len(nodes), "edges": edges}


def ingest_entities(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]] | None = None,
    *,
    source: str = _SOURCE,
    domain: str = _DOMAIN,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int] | None:
    """Write typed OWL nodes (+ edges) into epistemic-graph via the fast engine client.

    ``entities``: ``[{"id":..., "type":<owl:Class>, ...props}]``.
    ``relationships``: ``[{"source":id, "target":id, "type":<link>}]``.
    Returns ``{"nodes":n, "edges":m}`` or ``None`` (no engine / failure; never raises).
    Delegates to the shared ``native_ingest`` primitive when present; otherwise uses the
    local txn fallback. ``client``/``graph`` may be injected (tests).
    """
    entities = [e for e in (entities or []) if e.get("id")]
    if not entities:
        return None
    # Prefer the shared fleet primitive when the engine is resolved for us.
    if client is None:
        try:
            from agent_utilities.knowledge_graph.memory.native_ingest import (
                ingest_entities as _shared,
            )

            return _shared(
                entities, relationships, source=source, domain=domain, graph=graph
            )
        except Exception as e:  # noqa: BLE001 — primitive absent -> local fallback
            logger.debug("KG ingest: shared primitive unavailable: %s", e)
        client, graph = _native_client()
    if client is None:
        return None
    return _write_nodes(client, graph or _DEFAULT_GRAPH, entities, relationships)


def ingest_documents(
    documents: list[dict[str, Any]],
    *,
    source: str = _SOURCE,
    domain: str = _DOMAIN,
    client: Any | None = None,
    graph: str | None = None,
) -> dict[str, int] | None:
    """Write text records as ``:Document`` nodes (semantic-search fodder), best-effort."""
    documents = [d for d in (documents or []) if d.get("id") and d.get("text")]
    if not documents:
        return None
    if client is None:
        try:
            from agent_utilities.knowledge_graph.memory.native_ingest import (
                ingest_documents as _shared,
            )

            return _shared(documents, source=source, domain=domain, graph=graph)
        except Exception as e:  # noqa: BLE001 — primitive absent -> local fallback
            logger.debug("KG ingest: shared primitive unavailable: %s", e)
        client, graph = _native_client()
    if client is None:
        return None
    nodes = [{**d, "type": "Document"} for d in documents]
    return _write_nodes(client, graph or _DEFAULT_GRAPH, nodes, None)


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
        "type": "Portfolio",
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
                "type": "Position",
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
            {"id": inst_id, "type": "Instrument", "name": symbol, "symbol": symbol}
        )
        rels.append({"source": pos_id, "target": inst_id, "type": "ofInstrument"})
        rels.append(
            {
                "source": _portfolio_id(exchange),
                "target": pos_id,
                "type": "holdsPosition",
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
        {"id": inst_id, "type": "Instrument", "name": symbol, "symbol": symbol},
        {
            "id": q_id,
            "type": "Quote",
            "name": f"{symbol} quote",
            "symbol": symbol,
            "bid": quote.get("bid"),
            "ask": quote.get("ask"),
            "last": quote.get("last"),
            "volume": quote.get("volume"),
            "barTimestamp": ts or None,
        },
    ]
    rels = [{"source": q_id, "target": inst_id, "type": "ofInstrument"}]
    return entities, rels


def map_bars(symbol: str, bars: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Map OHLCV-shaped dicts → :MarketBar timeseries (+ :Instrument) nodes and links."""
    if not symbol:
        return [], []
    inst_id = _instrument_id(symbol)
    entities: list[dict] = [
        {"id": inst_id, "type": "Instrument", "name": symbol, "symbol": symbol}
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
                "type": "MarketBar",
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
        rels.append({"source": bar_id, "target": inst_id, "type": "ofInstrument"})
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
        "type": "Trade",
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
            "type": "settledInPortfolio",
        }
    ]
    if symbol:
        inst_id = _instrument_id(symbol)
        node["symbol"] = symbol
        entities.append(
            {"id": inst_id, "type": "Instrument", "name": symbol, "symbol": symbol}
        )
        rels.append({"source": t_id, "target": inst_id, "type": "tradesInstrument"})
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
) -> dict[str, int] | None:
    """List account + positions (+ optional quotes/bars for ``symbols``) off a live
    ExchangeBackend and push them into the KG as typed nodes. Best-effort / no-op safe.
    """
    entities: list[dict] = []
    rels: list[dict] = []

    try:
        acct = backend.get_account()
        e, r = map_account(_as_dict(acct))
        entities += e
        rels += r
    except Exception as e:  # noqa: BLE001
        logger.debug("KG ingest: account snapshot skipped: %s", e)

    try:
        positions = [_as_dict(p) for p in backend.get_positions()]
        e, r = map_positions(positions)
        entities += e
        rels += r
    except Exception as e:  # noqa: BLE001
        logger.debug("KG ingest: positions snapshot skipped: %s", e)

    for sym in symbols or []:
        try:
            e, r = map_quote(_as_dict(backend.get_quote(sym)))
            entities += e
            rels += r
        except Exception as e:  # noqa: BLE001
            logger.debug("KG ingest: quote %s skipped: %s", sym, e)
        if include_history:
            try:
                bars = [
                    _as_dict(b) for b in backend.get_historical(sym, period, interval)
                ]
                e, r = map_bars(sym, bars)
                entities += e
                rels += r
            except Exception as e:  # noqa: BLE001
                logger.debug("KG ingest: history %s skipped: %s", sym, e)

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
