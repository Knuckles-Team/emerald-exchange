---
name: emerald-exchange-kg-ingestion
skill_type: skill
description: >-
  Make Emerald Exchange records available to the knowledge graph through the connector's declared data
  sources: account and position snapshots (`emerald_exchange_get_account_snapshot`,
  `emerald_exchange_get_account_positions`), open positions (`emerald_exchange_get_positions`), and the
  bounded provider pages that carry a checkpoint. Use when the agent must plan or verify what the graph
  receives from this connector: which tool feeds which record type, and how the checkpoint advances. Do NOT use
  for one-off reads that are not persisted (use emerald-exchange-market-data) or to place orders
  (use emerald-exchange-order-execution).
license: MIT
tags: [emerald-exchange, knowledge-graph, ingestion, timeseries]
metadata:
  author: Knuckles-Team
  version: '0.2.0'
---
# Emerald Exchange to Knowledge Graph

The connector declares its data sources by tool name (`connector://resources`). The platform's source sync
calls each source tool with `mode: delta`, stores the `checkpoint` it returns, and writes typed records.

## When to use
- Plan which sources feed which record types.
- Check that a source returned a checkpoint and a stable record identity.
- Re-run a source from its last checkpoint after a failure.

## When NOT to use
- Reading a price or balance for an answer: `emerald-exchange-market-data`.
- Order actions: `emerald-exchange-order-execution`.

## Prerequisites & environment
Connect to the **`emerald-exchange`** MCP server. The active backend and mode come from the trading
configuration and default to the paper backend, which needs no credentials. Alpaca reads need the Alpaca
credentials in the operator configuration; provider reads need their provider key. Every tool here is
read-only and typed; there is no `action` argument. Never print a key.

## Sources
| Source tool | Record type | Needs |
|---|---|---|
| `emerald_exchange_get_account_snapshot` | Account with positions | Alpaca backend |
| `emerald_exchange_get_account_positions` | Position, with `position_id` from account and symbol | Alpaca backend |
| `emerald_exchange_get_positions` | Position | any backend |
| `emerald_exchange_get_csv_activities` | Activity | Alpaca backend, column mapping |
| `emerald_exchange_get_stock_bars`, `_get_stock_quote`, `_get_stock_news`, `_get_stock_dividends` | StockBar, StockQuote, StockNews, StockDividend | Alpaca backend |
| `emerald_exchange_get_company_records` | CompanyRecord | Alpaca backend, FMP key |
| `emerald_exchange_get_exchange_history` | ExchangeCandle | CCXT backend |
| `emerald_exchange_get_multi_asset_records` | MultiAssetRecord | provider key per kind |

## Procedure
1. Run the source with `mode` set to `delta` and the previous checkpoint in `since`.
2. Confirm the response holds records and a new `checkpoint` (and `next_page_token` for paged sources).
3. Page until `next_page_token` is empty, then store the last checkpoint.

## Gotchas
- A repeated run with the same checkpoint must not duplicate records; identities are hashes of tenant, source, account and event id.
- A source on the wrong backend is refused; read `emerald_exchange_exchanges` first.
