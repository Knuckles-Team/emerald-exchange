# Usage — API / CLI / MCP

`emerald-exchange` exposes the same capability three ways: as **MCP tools** an
agent calls, as a **Python API** the operator import, and as a **cockpit CLI**. The complete
tool surface and architecture are in [Overview](overview.md).

## As an MCP server

Once [deployed](deployment.md), the server registers action-routed tool domains.
Reads work against the in-process Paper backend with no configuration; live
execution requires explicit live-mode opt-in and per-venue credentials, and every
order clears the pre-trade risk guard first.

Every operation is its own typed tool; no tool takes an `action` argument.

| Domain | Tools |
|---|---|
| Market data and account | `emerald_exchange_get_quote`, `emerald_exchange_get_historical`, `emerald_exchange_exchanges`, `emerald_exchange_get_account`, `emerald_exchange_get_positions`, and the other `emerald_exchange_*` reads |
| Orders | `emerald_orders_submit`, `emerald_orders_cancel`, `emerald_orders_status`, `emerald_orders_halt`, `emerald_orders_resume` |
| Risk | `emerald_risk_status`, `emerald_risk_drawdown_check`, `emerald_risk_daily_loss_check`, `emerald_risk_kelly`, `emerald_risk_bayesian_kelly`, `emerald_risk_empirical_kelly`, `emerald_risk_limits` |
| Signals | `emerald_signals_regime`, `emerald_signals_alpha`, `emerald_signals_fuse`, `emerald_signals_surveillance`, `emerald_signals_insider_equilibrium` |
| Strategy | `emerald_strategy_backtest`, `emerald_strategy_list`, `emerald_strategy_promote`, `emerald_strategy_export` |
| Crypto | `emerald_crypto_funding_rates`, `emerald_crypto_whale_alerts`, `emerald_crypto_on_chain`, `emerald_crypto_arb_scan`, `emerald_crypto_cointegration` |
| Derivatives | `emerald_derivatives_implied_vol`, `emerald_derivatives_smile`, `emerald_derivatives_calibrate`, `emerald_derivatives_vol_arb` (SABR) |
| Market making | `emerald_market_making_quote`, `emerald_market_making_fee`, `emerald_market_making_backtest`, `emerald_market_making_validate`, `emerald_market_making_pbo`, `emerald_market_making_forensic`, `emerald_market_making_brier` |
| Statistical arbitrage | `emerald_statarb_ou_signal`, `emerald_statarb_dynamic_beta` |
| Debate | `emerald_debate_start`, `emerald_debate_submit_argument`, `emerald_debate_risk_veto`, `emerald_debate_consensus`, `emerald_debate_history` |
| Prediction markets | `emerald_prediction_markets_fetch_open_meteo_ensemble`, `emerald_prediction_markets_fetch_polymarket_orderbook`, `emerald_prediction_markets_fetch_kalshi_orderbook`, `emerald_prediction_markets_evaluate_event_arbitrage` |
| Fundamentals | `emerald_fundamentals_filings`, `emerald_fundamentals_financials`, `emerald_fundamentals_risk_factors`, `emerald_fundamentals_mdna`, `emerald_fundamentals_full_text_search`, `emerald_fundamentals_standardize`, `emerald_fundamentals_forensic_screen` |
| Wallet intelligence | `emerald_wallet_intel_rank_wallets`, `emerald_wallet_intel_wallet_profile`, `emerald_wallet_intel_smart_money_convergence`, `emerald_wallet_intel_exit_behavior` |

Submit, cancel and halt are destructive: the server asks the caller to confirm, or
the caller passes `confirm: true` when its client cannot be asked.

Example agent prompts that map onto these tools:

- *"Get the latest quote for AAPL"* → `emerald_exchange_get_quote`
- *"What position size does Kelly suggest for this trade?"* → `emerald_risk_kelly`
- *"Halt all trading now"* → `emerald_orders_halt` (the kill switch)
- *"Run a forensic screen on ticker XYZ"* → `emerald_fundamentals_forensic_screen`

## As a Python API

The exchange backends are reached through the `create_backend` factory and the
`ExchangeBackend` protocol. Backends default to **Paper**, so the API is safe to
use with no credentials.

```python
from emerald_exchange.backends import create_backend, TradingMode

# Paper backend — fully self-contained, no credentials required
backend = create_backend("paper", mode=TradingMode.PAPER)
backend.connect()

# Reads
quote = backend.get_quote("AAPL")  # latest bid/ask/last
account = backend.get_account()  # cash, equity, buying power
positions = backend.get_positions()  # open positions
```

Validate an order against the risk guard before submission:

```python
from emerald_exchange.risk_guards import RiskGuard

guard = RiskGuard()
decision = guard.pre_trade_check(
    symbol="AAPL",
    side="buy",
    quantity=10,
    price=quote.last,
    account=account,
)
print(decision)  # approved with limits, or blocked with a reason
```

Switch to a live venue by selecting its backend and supplying credentials via the
`trading` config block (see the [Configuration schema](config_schema.md)):

```python
backend = create_backend(
    "alpaca",
    {"api_key": "...", "secret_key": "..."},
    mode=TradingMode.PAPER,  # Alpaca paper trading is free
)
```

## As a CLI

The **cockpit** (`emerald-cockpit`) is a GUI-free, read-only trading cockpit. It
renders a structured snapshot — engine status, account and positions, risk
(kill-switch / drawdown / daily-loss), watchlist quotes, and recent signals — as a
plain-text or `rich` table. It is offline-safe: a missing engine renders
`engine: offline` and a backend error renders an empty panel rather than raising.

```bash
emerald-cockpit                     # render the current cockpit snapshot
```

The MCP server itself is launched with `emerald-exchange-mcp` and the A2A agent
server with `emerald-exchange-agent` — both are covered in [Deployment](deployment.md).
