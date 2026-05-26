# Emerald Exchange — Config Schema

The `trading` section in `~/.config/agent-utilities/config.json` controls all trading behavior.

## Full Schema

```json
{
  "trading": {
    "enabled": true,
    "default_exchange": "paper",
    "default_mode": "paper",
    "risk_limits": {
      "max_position_pct": 0.02,
      "max_portfolio_drawdown_pct": 0.10,
      "max_daily_loss_pct": 0.03,
      "regime_shift_halt": true,
      "require_human_approval_live": true
    },
    "exchanges": {
      "paper": {
        "enabled": true,
        "initial_cash": 100000.0
      },
      "alpaca": {
        "enabled": false,
        "api_key_env": "ALPACA_API_KEY",
        "secret_key_env": "ALPACA_SECRET_KEY",
        "base_url": "https://paper-api.alpaca.markets"
      },
      "ccxt:binance": {
        "enabled": false,
        "exchange_id": "binance",
        "api_key_env": "BINANCE_API_KEY",
        "secret_env": "BINANCE_SECRET"
      },
      "ccxt:coinbase": {
        "enabled": false,
        "exchange_id": "coinbase",
        "api_key_env": "COINBASE_API_KEY",
        "secret_env": "COINBASE_SECRET"
      },
      "ccxt:kraken": {
        "enabled": false,
        "exchange_id": "kraken",
        "api_key_env": "KRAKEN_API_KEY",
        "secret_env": "KRAKEN_SECRET"
      },
      "freqtrade": {
        "enabled": false,
        "api_url": "http://localhost:8080",
        "api_key_env": "FREQTRADE_API_KEY"
      }
    },
    "signal_fusion": {
      "default_method": "bayesian",
      "min_confidence": 0.6,
      "signal_sources": ["momentum", "mean_reversion", "volatility", "ml_prediction"]
    },
    "strategy_lifecycle": {
      "auto_promote": false,
      "min_backtest_sharpe": 1.5,
      "min_paper_days": 30,
      "export_formats": ["pinescript", "mql5", "tdx"]
    },
    "monitoring": {
      "risk_check_interval_minutes": 5,
      "portfolio_snapshot_interval_minutes": 15,
      "enable_alerts": true,
      "alert_channels": ["kg_event", "log"]
    }
  }
}
```

## Exchange Backend Abstraction — CONCEPT:EE-002

All exchanges implement the same `ExchangeBackend` Protocol. Switch backends by changing `default_exchange`:

| Backend | `default_exchange` | Assets | Free Tier | Library |
|---------|-------------------|--------|-----------|---------|
| Paper   | `paper`           | equity, crypto, forex | ✅ Default | Built-in |
| Alpaca  | `alpaca`          | equity, crypto | ✅ Free paper | `alpaca-py` |
| Binance | `ccxt:binance`    | crypto | ✅ Sandbox | `ccxt` |
| Coinbase | `ccxt:coinbase`  | crypto | ✅ Sandbox | `ccxt` |
| Kraken  | `ccxt:kraken`     | crypto | ✅ Sandbox | `ccxt` |
| Freqtrade | `freqtrade`    | crypto | ✅ OSS | REST API |

### Adding a new exchange

1. Create a class implementing `ExchangeBackend` Protocol in `backends.py`
2. Register it in `BACKEND_REGISTRY`
3. Add config entry under `exchanges`
4. Secrets resolve via `_env` suffix → `os.environ`

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ALPACA_API_KEY` | Alpaca API key | Only if using Alpaca |
| `ALPACA_SECRET_KEY` | Alpaca secret | Only if using Alpaca |
| `BINANCE_API_KEY` | Binance API key | Only if using Binance |
| `BINANCE_SECRET` | Binance secret | Only if using Binance |
| `COINBASE_API_KEY` | Coinbase API key | Only if using Coinbase |
| `COINBASE_SECRET` | Coinbase secret | Only if using Coinbase |
| `KRAKEN_API_KEY` | Kraken API key | Only if using Kraken |
| `KRAKEN_SECRET` | Kraken secret | Only if using Kraken |
| `FREQTRADE_API_KEY` | Freqtrade REST key | Only if using Freqtrade |
