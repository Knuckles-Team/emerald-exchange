# Emerald Exchange Market Research

Research markets through the emerald-exchange MCP server — crypto funding, whale and on-chain data, arbitrage scans and cointegration, prediction-market orderbooks and ensemble-forecast arbitrage, SEC filings and fundamentals with a forensic screen, and prediction-market wallet intelligence — one typed tool per operation (emerald_crypto_*, emerald_prediction_markets_*, emerald_fundamentals_*, emerald_wallet_intel_*). Use when the agent must gather research inputs before an analysis or a trade. Every tool reads; none places an order (use emerald-exchange-order-execution).

# Emerald Exchange — Market Research

Read-only research tools, one per operation. Optional data sources degrade to an
error payload instead of failing the server: filings need an SEC identity
(`EDGAR_IDENTITY`) and the optional filings dependency; wallet intelligence needs a
trades dataset (`POLY_TRADES_PATH`).

## When to use
- Crypto funding rates, whale alerts, on-chain activity, cross-venue arbitrage, cointegration.
- Prediction-market orderbooks, ensemble weather forecasts, event arbitrage.
- Company filings, statements, risk factors, MD&A, full-text search, forensic screen.
- Smart-money wallets, wallet profiles, convergence on a token, exit behaviour.

## When NOT to use
- Quotes, bars and account reads → `emerald-exchange-market-data`.
- Signals, backtests and pricing → `emerald-exchange-quant-analysis`.
- Orders → `emerald-exchange-order-execution`.

## Tools
| Tool | Reads |
|------|-------|
| `emerald_crypto_funding_rates` | Perpetual funding rate for a pair |
| `emerald_crypto_whale_alerts` | Large on-chain transfers |
| `emerald_crypto_on_chain` | On-chain volume and active addresses |
| `emerald_crypto_arb_scan` | Cross-exchange arbitrage between two venues |
| `emerald_crypto_cointegration` | Cointegration of a pair |
| `emerald_prediction_markets_fetch_open_meteo_ensemble` | Ensemble weather forecast for a location |
| `emerald_prediction_markets_fetch_polymarket_orderbook` | Polymarket orderbook for an event |
| `emerald_prediction_markets_fetch_kalshi_orderbook` | Kalshi orderbook for a ticker |
| `emerald_prediction_markets_evaluate_event_arbitrage` | Dual-platform event arbitrage |
| `emerald_fundamentals_filings` | Latest filings of a form |
| `emerald_fundamentals_financials` | Standardized statement |
| `emerald_fundamentals_risk_factors` | Item 1A, this year and prior year |
| `emerald_fundamentals_mdna` | Item 7 MD&A, this year and prior year |
| `emerald_fundamentals_full_text_search` | Full-text phrase search |
| `emerald_fundamentals_standardize` | Two fiscal years in the forensic schema |
| `emerald_fundamentals_forensic_screen` | Standardize, then the engine forensic verdict |
| `emerald_wallet_intel_rank_wallets` | Smart-money copy-trade targets |
| `emerald_wallet_intel_wallet_profile` | Per-wallet stats and open positions |
| `emerald_wallet_intel_smart_money_convergence` | Target wallets on the same side of a token |
| `emerald_wallet_intel_exit_behavior` | Exits before resolution, profit captured |

## Recipes
Forensic screen for one ticker:
```json
{"tool": "emerald_fundamentals_forensic_screen", "arguments": {"ticker": "AAPL"}}
```
Rank wallets:
```json
{"tool": "emerald_wallet_intel_rank_wallets", "arguments": {"min_trades": 20, "top_k": 10}}
```

## Gotchas
- Some crypto and orderbook tools return simulated placeholders and say so in `note`.
- Event arbitrage is refused (`not_served`) until the engine serves the analysis.

## Related
- `emerald-exchange-quant-analysis` — analyse what you gathered.
