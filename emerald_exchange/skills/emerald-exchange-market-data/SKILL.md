---
name: emerald-exchange-market-data
skill_type: skill
description: >-
  Read market data through the emerald-exchange MCP server: quotes, OHLCV history, exchange backends, account equity and positions, via emerald_market_data and emerald_portfolio. Use to fetch a quote, pull bars, or read positions. Do NOT use for orders (emerald-exchange-order-execution) or KG ingest (emerald-exchange-kg-ingestion).
license: MIT
tags: [emerald-exchange, market-data, quotes, ohlcv, trading, mcp]
metadata:
  author: Knuckles-Team
  version: '0.1.0'
---
# Emerald Exchange — Market Data

Scope: Read market data through the emerald-exchange MCP server — top-of-book quotes, OHLCV history, and the available exchange backends — via the domain-typed emerald_market_data and emerald_portfolio tools (not raw exchange SDK calls). Use when the agent must fetch a live quote for a symbol, pull historical bars for backtesting/analysis, list which exchange backends are wired, or read account equity/positions. Do NOT use to place or cancel orders (use emerald-exchange-order-execution) or to push records into the knowledge graph (use emerald-exchange-kg-ingestion).

Domain-typed, backend-abstracted read access to market data across every wired
exchange (paper, Alpaca, Binance, CCXT, …). One tool surface regardless of the
underlying venue.

## When to use
- Get a current quote (bid/ask/last/volume) for a symbol.
- Pull OHLCV historical bars for a symbol over a period/interval.
- List the available exchange backends and the active one + mode.
- Read the account summary (equity, cash, buying power) or open positions.

## When NOT to use
- Submitting, cancelling, or checking orders → `emerald-exchange-order-execution`.
- Pushing quotes/positions/bars into the knowledge graph as typed nodes →
  `emerald-exchange-kg-ingestion`.
- Strategy signals, statarb, derivatives pricing → the respective emerald tools
  (`emerald_signals`, `emerald_statarb`, `emerald_derivatives`).

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`emerald-exchange`** MCP server.
The active backend + mode come from `config.json` → `trading.default_exchange` /
`trading.default_mode` (defaults to `paper`, so no credentials are needed to start).

| Variable | Required | Notes |
|----------|----------|-------|
| (paper mode) | — | No credentials; local simulation backend |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | for alpaca | Live/paper equities |
| `BINANCE_API_KEY` / `BINANCE_SECRET` | for binance | Crypto |

`MCP_TOOL_MODE` (`condensed`|`verbose`|`both`) selects the condensed `action`-routed
surface (used below) vs. the 1:1 verbose tools over the backend methods.

## Steps

1. Confirm the active venue by calling `emerald_market_data` with `{"action": "exchanges"}`. Verify the response names the active backend and `mode` (paper or live).
2. Fetch the quote with `emerald_market_data` `{"action": "quote", "symbol": "<symbol>"}`. Verify the response has bid, ask and last values for that symbol.
3. For bars call `emerald_market_data` `{"action": "historical", "symbol": "<symbol>", "period": "1mo", "interval": "1d"}`. Verify the bar count is within the 50-bar cap and the dates cover the window.
4. Read the account with `emerald_portfolio` `{"action": "account"}`. Verify the response shows equity and cash.
5. List holdings with `emerald_portfolio` `{"action": "positions"}`. Verify each position has a symbol and quantity, or that the list is empty for a flat account.

## Failure recovery

| Failure | Cause | Recovery |
|---------|-------|----------|
| Quote is empty or an error for a symbol | Symbol format does not match the active backend (for example `BTC/USD` versus `BTCUSDT`) | Call `emerald_market_data` `{"action": "exchanges"}` to see the backend, then retry with that backend's symbol format |
| Authentication error on a live backend | `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` or `BINANCE_API_KEY`/`BINANCE_SECRET` unset | Report which variable is missing, or switch to the paper backend by setting `trading.default_mode` to `paper` in `config.json` |
| Prices look like round placeholders | The backend is paper mode, so quotes are simulated | Check `mode` from the `exchanges` action and label the data as simulated in the report |

## Tools & actions
| Condensed tool | Actions |
|----------------|---------|
| `emerald_market_data` | `quote`, `historical`, `exchanges` |
| `emerald_portfolio` | `positions`, `account` |

### Key parameters
- `symbol` — required for `quote` and `historical`.
- `period` — history lookback (e.g. `1d`, `1mo`, `1y`); default `1y`.
- `interval` — bar size (e.g. `1m`, `1h`, `1d`); default `1d`.

## Recipes
Current quote:
```json
{"action": "quote", "symbol": "AAPL"}
```
Daily bars for the last month:
```json
{"action": "historical", "symbol": "BTC/USD", "period": "1mo", "interval": "1d"}
```
List backends / active venue:
```json
{"action": "exchanges"}
```

## Gotchas
- `historical` is capped to the first 50 bars in the condensed response — narrow the
  `period`/`interval` if you need a specific window rather than expecting the full series.
- In `paper` mode quotes/prices are simulated placeholders; do not treat them as real
  marks. Check `emerald_market_data action=exchanges` to confirm the active `mode`.
- Symbol conventions differ per backend (e.g. `BTC/USD` on CCXT vs `BTCUSDT` on Binance);
  pass the symbol as the active backend expects it.

## Related
- `emerald-exchange-order-execution` — act on this data (submit/cancel orders).
- `emerald-exchange-kg-ingestion` — persist quotes/positions/bars into the KG.
