---
name: emerald-exchange-kg-ingestion
description: >-
  Natively ingest live Emerald Exchange trading state into the epistemic-graph
  knowledge graph as typed OWL nodes — :Portfolio, :Position, :Instrument, :Quote,
  and :MarketBar (OHLCV timeseries) — via the emerald_ingest_snapshot MCP tool.
  Use when the agent must snapshot the current account, open positions, and
  optionally quotes/history for given symbols into the KG so they become
  queryable/linked knowledge. Do NOT use for one-off reads that shouldn't be
  persisted (use emerald-exchange-market-data) or to place orders
  (use emerald-exchange-order-execution).
license: MIT
tags: [emerald-exchange, knowledge-graph, ingestion, kg, timeseries, mcp]
metadata:
  author: Genius
  version: '0.1.0'
---
# Emerald Exchange — Knowledge-Graph Ingestion

Wire-First native ingestion: pull a live snapshot off the active exchange backend and
push it into the ONE epistemic-graph as typed nodes + links, so trading state becomes
queryable knowledge (which instruments a portfolio holds, price history per instrument,
etc.). Best-effort — no-ops cleanly when no KG engine is reachable.

## When to use
- Snapshot the current account (:Portfolio) and open positions (:Position + :Instrument)
  into the KG.
- Also capture live quotes (:Quote) and OHLCV history (:MarketBar timeseries) for a set
  of symbols in the same push.
- Build up a queryable graph of holdings ↔ instruments ↔ price bars for later analysis.

## When NOT to use
- Transient reads you don't want persisted → `emerald-exchange-market-data`.
- Submitting/cancelling orders → `emerald-exchange-order-execution`.
- Ingesting from a different source/venue not fronted by this MCP server.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`emerald-exchange`** MCP server. Ingestion
targets a running graph-os / epistemic-graph engine; with none reachable the tool returns
`{"ingested": null}` and the connector keeps working. The active backend/mode is the one
configured under `config.json` → `trading` (default `paper`).

| Variable | Required | Notes |
|----------|----------|-------|
| a reachable epistemic-graph engine | for a non-null result | Else clean no-op |
| exchange creds | for `live` snapshots | Paper mode needs none |

## Tools & actions
| Tool | Purpose |
|------|---------|
| `emerald_ingest_snapshot` | List account + positions (+ optional quotes/bars) → typed KG nodes |

### Key parameters
- `symbols` — comma-separated tickers to also snapshot as :Quote nodes (e.g. `"AAPL,BTC/USD"`).
- `include_history` — also pull OHLCV bars → :MarketBar timeseries per symbol (default false).
- `period` / `interval` — history window/bar size when `include_history` is true.

## Recipes
Snapshot account + positions only:
```json
{}
```
Snapshot plus quotes for two symbols:
```json
{"symbols": "AAPL,BTC/USD"}
```
Snapshot plus a month of daily bars per symbol:
```json
{"symbols": "AAPL", "include_history": true, "period": "1mo", "interval": "1d"}
```

## Gotchas
- Node ids are deterministic — `emerald:<class>:<extId>` (e.g. `emerald:instrument:AAPL`,
  `emerald:position:paper:AAPL`) — so re-ingesting MERGEs/updates the same nodes rather
  than duplicating them; run it repeatedly to keep the graph fresh.
- `include_history` can write many :MarketBar nodes (one per bar); keep `period`/`interval`
  sane for large universes.
- A null `ingested` field means no engine was reachable, **not** an error — the tool is
  intentionally best-effort and never raises.
- `type` on every node matches the federated ontology (emerald.ttl / quant.ttl); the
  :Instrument/:Quote/:MarketBar classes come from this package's `emerald` ontology leg.

## Related
- `emerald-exchange-market-data` / `emerald-exchange-order-execution` — the read/act tools
  whose records this skill persists.
- The declarative `connectors/mcp_source_presets.json` preset mirrors open positions as
  documents for the central `source_sync` path.
