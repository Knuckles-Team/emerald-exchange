---
name: emerald-exchange-market-data
skill_type: skill
description: >-
  Read market data and account state through the emerald-exchange read tools: list the exchange backends
  (`emerald_exchange_exchanges`), quote a symbol (`emerald_exchange_get_quote`), read OHLCV bars
  (`emerald_exchange_get_historical`), and read account balances and open positions
  (`emerald_exchange_get_account`, `emerald_exchange_get_positions`). Use when the agent needs a current quote,
  history for analysis, or equity and positions on the active backend. Do NOT use for Alpaca feed-labelled
  pages (use emerald-exchange-stock-reference), for FX, commodity or exchange candles (use
  emerald-exchange-multi-asset), or to place orders (use emerald-exchange-order-execution).
license: MIT
tags: [emerald-exchange, market-data, quotes, ohlcv]
metadata:
  author: Knuckles-Team
  version: '0.2.0'
---
# Emerald Exchange Market Data

One read surface over every wired backend (paper, Alpaca, CCXT venues). Say which backend and mode
answered each read.

## When to use
- Latest quote (bid, ask, last, volume) of one symbol.
- OHLCV bars of one symbol for a period and interval.
- Which backends exist, which is active and in what mode.
- Equity, cash and buying power; open positions.

## When NOT to use
- Alpaca pages that need an explicit feed, adjustment and license tag: `emerald-exchange-stock-reference`.
- Exchange candles, FX, commodities, property: `emerald-exchange-multi-asset`.
- Order status or any order action: `emerald-exchange-order-execution`.
- Statement import and account snapshots: `emerald-exchange-account-intake`.

## Prerequisites & environment
Connect to the **`emerald-exchange`** MCP server. The active backend and mode come from the trading
configuration and default to the paper backend, which needs no credentials. Alpaca reads need the Alpaca
credentials in the operator configuration; provider reads need their provider key. Every tool here is
read-only and typed; there is no `action` argument. Never print a key.

## Tools
| Tool | Arguments | Returns |
|---|---|---|
| `emerald_exchange_exchanges` | none | `available`, `active`, `mode` |
| `emerald_exchange_get_quote` | `symbol` | `symbol`, `bid`, `ask`, `last`, `volume`, `timestamp` |
| `emerald_exchange_get_historical` | `symbol`, `period` (default `1y`), `interval` (default `1d`) | bars with `timestamp`, `open`, `high`, `low`, `close`, `volume` |
| `emerald_exchange_get_account` | none | `equity`, `cash`, `buying_power`, `margin_used`, `currency`, `exchange`, `account_id` |
| `emerald_exchange_get_positions` | none | positions with `symbol`, `qty`, `avg_entry_price`, `current_price`, `unrealized_pnl`, `side` |

## Procedure
1. Call `emerald_exchange_exchanges` first when the backend matters to the answer.
2. Read the quote or bars; quote the `timestamp` of what you report.
3. For account questions read `get_account` and `get_positions` together so equity and positions agree.

## Gotchas
- Paper mode returns simulated data. Never present it as a live price or balance.
- Period and interval strings follow the backend (for example `1mo`, `1d`, `1h`).
