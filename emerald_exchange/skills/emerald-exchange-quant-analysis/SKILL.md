---
name: emerald-exchange-quant-analysis
skill_type: skill
description: >-
  Run quantitative analyses through the emerald-exchange MCP server — signal
  regime, fusion and surveillance, strategy backtests, OU stat-arb bands and
  dynamic hedge beta, SABR volatility surfaces, market-making quotes and backtest
  validation, and the bull/bear trading debate — one typed tool per analysis
  (emerald_signals_*, emerald_strategy_*, emerald_statarb_*, emerald_derivatives_*,
  emerald_market_making_*, emerald_debate_*). Use when the agent must measure a
  signal, validate a strategy, price volatility, or argue a trade before it is
  sized. Every analysis is decision-only and never places an order; to trade use
  emerald-exchange-order-execution.
license: MIT
tags: [emerald-exchange, quant, signals, backtest, derivatives, market-making, mcp]
metadata:
  author: Knuckles-Team
  version: '0.1.0'
---
# Emerald Exchange — Quant Analysis

The analyses run in the engine; each tool takes typed inputs and returns a
measurement or a decision. None places an order. An unreachable engine returns
its requirement error; an analysis the engine does not serve yet returns
`{"error": "not_served", "method": ...}`.

## When to use
- Detect the market regime or fuse directional signals with stored priors.
- Score informed-flow surveillance or model an insider equilibrium (defensive).
- Backtest a returns series and write the measured priors back to the graph.
- Compute OU stat-arb bands or a Kalman hedge beta.
- Price a SABR smile, calibrate it, or find rich/cheap strikes.
- Compute market-making quotes, validate backtests, score forecasts.
- Run a bull/bear debate on a hypothesis with a risk-officer veto.

## When NOT to use
- Placing, cancelling or halting orders → `emerald-exchange-order-execution`.
- Quotes, bars and account reads → `emerald-exchange-market-data`.
- Crypto, prediction-market, filings and wallet research → `emerald-exchange-market-research`.

## Tools
| Tool | Does |
|------|------|
| `emerald_signals_regime` | Regime from `close_prices` |
| `emerald_signals_alpha` | Alpha factors for a `ticker` |
| `emerald_signals_fuse` | Bayesian fusion of `directions` with stored priors |
| `emerald_signals_surveillance` | Informed-flow surveillance scores from a book/flow window |
| `emerald_signals_insider_equilibrium` | Insider equilibrium under legal risk |
| `emerald_strategy_backtest` | Deflated Sharpe, hit rate and PBO of `returns`; writes priors |
| `emerald_strategy_list` | Strategies in the graph |
| `emerald_strategy_promote` | Promote a strategy stage |
| `emerald_strategy_export` | Export a strategy (PineScript, MQL5, TDX) |
| `emerald_statarb_ou_signal` | OU stat-arb bands from a `spread` |
| `emerald_statarb_dynamic_beta` | Kalman hedge beta from asset and market returns |
| `emerald_derivatives_implied_vol` | One-strike SABR implied vol |
| `emerald_derivatives_smile` | SABR smile across `strikes` |
| `emerald_derivatives_calibrate` | Calibrate SABR to `market_vols` |
| `emerald_derivatives_vol_arb` | Rich/cheap strikes against the SABR-fair smile |
| `emerald_market_making_quote` | Intended quotes for one `book` update |
| `emerald_market_making_fee` | Venue fee for a fill |
| `emerald_market_making_backtest` | Event-driven L2-queue backtest |
| `emerald_market_making_validate` | Performance, deflated Sharpe, purged CPCV |
| `emerald_market_making_pbo` | Probability of backtest overfit |
| `emerald_market_making_forensic` | Two-year forensic accounting screen |
| `emerald_market_making_brier` | Brier score of `forecasts` vs `outcomes` |
| `emerald_debate_start` | Start a debate on a `hypothesis` |
| `emerald_debate_submit_argument` | Add a bull or bear argument |
| `emerald_debate_risk_veto` | Risk-officer veto |
| `emerald_debate_consensus` | Debate consensus so far |
| `emerald_debate_history` | Past debates |

## Recipes
Fuse two signals:
```json
{"tool": "emerald_signals_fuse", "arguments": {"ticker": "AAPL", "directions": {"ofi": 1, "rsi": -1}}}
```
Backtest and write priors:
```json
{"tool": "emerald_strategy_backtest", "arguments": {"strategy_id": "sig:ofi", "returns": [0.01, -0.004, 0.02, 0.015]}}
```
SABR smile:
```json
{"tool": "emerald_derivatives_smile", "arguments": {"f": 100, "strikes": [90, 100, 110], "t": 0.5, "alpha": 0.2}}
```

## Gotchas
- Market-making quotes are decisions, not orders; live execution stays behind the
  order tools and the risk guard.
- Surveillance and insider-equilibrium tools are defensive: they measure informed
  flow and enforcement levers, never conceal trades.

## Related
- `emerald-exchange-order-execution` — act on an analysis.
- `emerald-exchange-market-research` — external research inputs.
