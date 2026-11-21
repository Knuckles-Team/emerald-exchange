---
name: emerald-exchange-multi-asset
skill_type: skill
description: >-
  Read non-equity market data: bounded exchange candles from a CCXT backend
  (`emerald_exchange_get_exchange_history`) and provider observations for foreign exchange, commodities,
  spot gold and property valuation (`emerald_exchange_get_multi_asset_records`). Use when the agent needs crypto
  candles with a stable identity, an FX rate, a commodity bar, a gold spot price or a property valuation. Do NOT
  use for equities (use emerald-exchange-market-data or emerald-exchange-stock-reference) or to place orders.
license: MIT
tags: [emerald-exchange, crypto, fx, commodities, real-estate]
metadata:
  author: Knuckles-Team
  version: '0.2.0'
---
# Emerald Exchange Multi-Asset

## When to use
- One page of candles from a CCXT exchange, with a page token for the next page.
- An FX rate (`kind` `fx`, with `base` and `quote`).
- A commodity bar (`kind` `commodity`, with `dataset`, `symbol`, `start`, `end`).
- A gold spot price (`kind` `commodity_spot`).
- A property valuation (`kind` `real_estate`, with `attom_id` and `max_age_days`).

## When NOT to use
- Equities: `emerald-exchange-market-data`, `emerald-exchange-stock-reference`.

## Prerequisites & environment
Connect to the **`emerald-exchange`** MCP server. The active backend and mode come from the trading
configuration and default to the paper backend, which needs no credentials. Alpaca reads need the Alpaca
credentials in the operator configuration; provider reads need their provider key. Every tool here is
read-only and typed; there is no `action` argument. Never print a key.

## Tools
| Tool | Key arguments | Returns |
|---|---|---|
| `emerald_exchange_get_exchange_history` | `symbol`, `start`, `end`, `interval`, `license_tag`, `mode`, `limit`, `page_token` | `candles`, `next_page_token`, `checkpoint` |
| `emerald_exchange_get_multi_asset_records` | `kind`, `tenant_id`, `source_id`, `license_tag`, `mode`, plus the kind's own arguments | `records`, `checkpoint` |

## Procedure
1. For candles, confirm a CCXT backend is active with `emerald_exchange_exchanges`.
2. For multi-asset reads, give only the arguments of the chosen `kind`.
3. Report the `license_tag` with the data and carry the checkpoint forward.

## Gotchas
- Each kind needs its own provider key in the environment; a missing key surfaces as a provider read failure.
- Provider errors are reported without detail on purpose; do not guess the cause.
