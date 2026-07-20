# Usage — API / CLI / MCP

`emerald-exchange` exposes the same capability three ways: as **MCP tools** an
agent calls, as a **Python API** you import, and as a **cockpit CLI**. The complete
tool surface and architecture are in [Overview](overview.md).

## As an MCP server

Once [deployed](deployment.md), the server registers action-routed tool domains.
Reads work against the in-process Paper backend with no configuration; live
execution requires explicit live-mode opt-in and per-venue credentials, and every
order clears the pre-trade risk guard first.

| Domain | Tool | Actions |
|---|---|---|
| Market data | `emerald_market_data` | quote, historical, exchanges |
| Orders | `emerald_orders` | submit, cancel, status, halt, resume |
| Portfolio | `emerald_portfolio` | positions, account |
| Risk | `emerald_risk` | status, drawdown_check, daily_loss_check, kelly, empirical_kelly, limits |
| Signals | `emerald_signals` | regime, alpha, fuse |
| Strategy | `emerald_strategy` | list, promote, export |
| Crypto | `emerald_crypto` | funding rates, whale alerts, arbitrage scan |
| Derivatives | `emerald_derivatives` | implied_vol, smile, calibrate, vol_arb (SABR) |
| Market making | `emerald_market_making` | quoting policy, brier |
| Statistical arbitrage | `emerald_statarb` | ou_signal, dynamic_beta |
| Prediction markets | `emerald_prediction_markets` | kalshi_events, polymarket_events, open_meteo_ensemble |
| Fundamentals | `emerald_fundamentals` | filings, financials, risk_factors, mdna, full_text_search, standardize, forensic_screen |
| Wallet intelligence | `emerald_wallet_intel` | rank_wallets, wallet_profile, smart_money_convergence, exit_behavior |

Example agent prompts that map onto these tools:

- *"Get the latest quote for AAPL"* → `emerald_market_data`
- *"What position size does Kelly suggest for this trade?"* → `emerald_risk`
- *"Halt all trading now"* → `emerald_orders(action="halt")` (the kill switch)
- *"Run a forensic screen on ticker XYZ"* → `emerald_fundamentals`

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
quote = backend.get_quote("AAPL")            # latest bid/ask/last
account = backend.get_account()              # cash, equity, buying power
positions = backend.get_positions()          # open positions
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
print(decision)        # approved with limits, or blocked with a reason
```

Switch to a live venue by selecting its backend and supplying credentials via the
`trading` config block (see the [Configuration schema](config_schema.md)):

```python
backend = create_backend(
    "alpaca",
    {"api_key": "...", "secret_key": "..."},
    mode=TradingMode.PAPER,        # Alpaca paper trading is free
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
