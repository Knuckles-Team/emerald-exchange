# Emerald Exchange Market Data

Read market data and account state through the emerald-exchange MCP server — quotes, OHLCV history, stock bars, news and dividends, company and multi-asset records, the available exchange backends, account and positions — via the typed emerald_exchange_* read tools (not raw exchange SDK calls). Use when the agent must fetch a live quote for a symbol, pull historical bars for backtesting or analysis, list which exchange backends are wired, or read account equity and positions. Do NOT use to place or cancel orders (use emerald-exchange-order-execution) or to push records into the knowledge graph (use emerald-exchange-kg-ingestion).

# Emerald Exchange — Market Data

Typed, backend-abstracted read access to market data across every wired
exchange (paper, Alpaca, Binance, CCXT, …). One tool per read operation,
regardless of the underlying venue. Every tool here is read-only.

## When to use
- Get a current quote (bid/ask/last/volume) for a symbol.
- Pull OHLCV historical bars for a symbol over a period/interval.
- List the available exchange backends and the active one + mode.
- Read the account summary (equity, cash, buying power) or open positions.
- Read stock bars, quotes, news and dividends, company records or multi-asset records.

## When NOT to use
- Submitting, cancelling, or checking orders → `emerald-exchange-order-execution`.
- Pushing quotes/positions/bars into the knowledge graph as typed nodes →
  `emerald-exchange-kg-ingestion`.
- Strategy signals, statarb, derivatives pricing → `emerald-exchange-quant-analysis`.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`emerald-exchange`** MCP server.
The active backend + mode come from `config.json` → `trading.default_exchange` /
`trading.default_mode` (defaults to `paper`, so no credentials are needed to start).

| Variable | Required | Notes |
|----------|----------|-------|
| (paper mode) | — | No credentials; local simulation backend |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | for alpaca | Live/paper equities |
| `BINANCE_API_KEY` / `BINANCE_SECRET` | for binance | Crypto |

## Tools
| Tool | Reads |
|------|-------|
| `emerald_exchange_get_quote` | Current quote for `symbol` |
| `emerald_exchange_get_historical` | OHLCV bars for `symbol`, `period`, `interval` |
| `emerald_exchange_get_exchange_history` | Paged exchange OHLCV history |
| `emerald_exchange_exchanges` | Available backends, the active one and its mode |
| `emerald_exchange_get_account` | Equity, cash, buying power |
| `emerald_exchange_get_account_snapshot` | Account snapshot records |
| `emerald_exchange_get_positions` | Open positions |
| `emerald_exchange_get_account_positions` | Account position records |
| `emerald_exchange_get_order_status` | Status of one order by `order_id` |
| `emerald_exchange_get_stock_bars` | Stock bars |
| `emerald_exchange_get_stock_quote` | Stock quote |
| `emerald_exchange_get_stock_news` | Stock news |
| `emerald_exchange_get_stock_dividends` | Stock dividends |
| `emerald_exchange_get_company_records` | Company profile, income, earnings, logo |
| `emerald_exchange_get_multi_asset_records` | FX, commodity and real-estate records |
| `emerald_exchange_get_csv_activities` | Account activities from a CSV export |

## Recipes
Current quote:
```json
{"tool": "emerald_exchange_get_quote", "arguments": {"symbol": "AAPL"}}
```
Daily bars for the last month:
```json
{"tool": "emerald_exchange_get_historical", "arguments": {"symbol": "BTC/USD", "period": "1mo", "interval": "1d"}}
```
List backends / active venue:
```json
{"tool": "emerald_exchange_exchanges", "arguments": {}}
```

## Gotchas
- In `paper` mode quotes/prices are simulated placeholders; do not treat them as real
  marks. Check `emerald_exchange_exchanges` to confirm the active `mode`.
- Symbol conventions differ per backend (e.g. `BTC/USD` on CCXT vs `BTCUSDT` on Binance);
  pass the symbol as the active backend expects it.

## Related
- `emerald-exchange-order-execution` — act on this data (submit/cancel orders).
- `emerald-exchange-kg-ingestion` — persist quotes/positions/bars into the KG.
