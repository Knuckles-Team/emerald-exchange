# Emerald Exchange Order Execution

Place, cancel, and check trading orders through the emerald-exchange MCP server with mandatory pre-trade risk validation, plus the emergency halt/resume kill switch and the risk checks and Kelly sizing that gate an order — one typed tool per operation (emerald_orders_submit, emerald_orders_cancel, emerald_orders_status, emerald_orders_halt, emerald_orders_resume, emerald_risk_*). Use when the agent must size and submit a market/limit order, cancel or status an existing order by id, check drawdown or daily loss, or halt all trading. Do NOT use to read quotes or positions (use emerald-exchange-market-data), and be deliberate in live mode — paper is the default. Do NOT bypass the risk guard with raw backend calls.

# Emerald Exchange — Order Execution

Backend-abstracted order management. **Every** order passes a pre-trade
`RiskGuard.pre_trade_check` (sizing, exposure, live-mode gating) before it reaches
the exchange, and a global kill switch can halt all trading instantly.

## When to use
- Size a position (Kelly, Bayesian Kelly, empirical Kelly) within the risk limits.
- Submit a market or limit order (buy/sell) with risk validation.
- Cancel an existing order by `order_id`, or check its status and fill.
- Check drawdown and daily loss against the limits; read the risk status.
- Emergency halt (kill switch) / resume of all trading.

## When NOT to use
- Reading quotes, history, positions, or account → `emerald-exchange-market-data`.
- Persisting executed trades into the KG → `emerald-exchange-kg-ingestion`.
- Signals, statarb, derivatives or market-making quotes → `emerald-exchange-quant-analysis`.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`emerald-exchange`** MCP server.
Mode + risk limits come from `config.json` → `trading.default_mode` (`paper`|`live`)
and `trading.risk_limits`. Default is `paper` — no credentials, simulated fills.

| Variable | Required | Notes |
|----------|----------|-------|
| (paper mode) | — | Simulated fills; safe to exercise freely |
| exchange creds (e.g. `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`) | for `live` | Real orders |
| `SCION_ALLOW_DESTRUCTIVE` | no | Operator setting: lets unattended runs submit, cancel and halt without a confirmation |

## Tools
| Tool | Does | Kind |
|------|------|------|
| `emerald_orders_submit` | Risk-checked order submit (`symbol`, `qty`, `side`, `order_type`, `limit_price`) | destructive |
| `emerald_orders_cancel` | Cancel an order by `order_id` | destructive |
| `emerald_orders_status` | Status, filled quantity and average price of an order | read |
| `emerald_orders_halt` | Kill switch: halt ALL trading | destructive |
| `emerald_orders_resume` | Resume trading after a halt | write |
| `emerald_risk_status` | Halted flag, equity, peak equity, exchange and mode | read |
| `emerald_risk_limits` | The configured risk limits | read |
| `emerald_risk_drawdown_check` | Drawdown against the limit | read |
| `emerald_risk_daily_loss_check` | Daily loss (`daily_pnl`) against the limit | read |
| `emerald_risk_kelly` | Point Kelly size (`win_rate`, `win_loss_ratio`) | read |
| `emerald_risk_bayesian_kelly` | Beta-posterior Kelly (`wins`, `losses`, `cost`, `fraction`) | read |
| `emerald_risk_empirical_kelly` | Monte-Carlo Kelly over `historical_returns` | read |

Destructive tools ask the caller to confirm. A client that cannot be asked passes
`confirm: true` deliberately; without either, the call returns
`{"cancelled": true, "operation": ...}` and nothing happens.

## Recipes
Size, then submit a limit buy:
```json
{"tool": "emerald_risk_kelly", "arguments": {"win_rate": 0.55, "win_loss_ratio": 1.5}}
{"tool": "emerald_orders_submit", "arguments": {"symbol": "AAPL", "side": "buy", "qty": 10, "order_type": "limit", "limit_price": 150.0, "confirm": true}}
```
Cancel an order:
```json
{"tool": "emerald_orders_cancel", "arguments": {"order_id": "PAPER-000001", "confirm": true}}
```
Emergency halt, later resume:
```json
{"tool": "emerald_orders_halt", "arguments": {"confirm": true}}
{"tool": "emerald_orders_resume", "arguments": {}}
```

## Gotchas
- The risk guard can **reject** (`approved: false` + `reason`/`risk_score`) or **resize**
  the order — the response's `filled_qty` may be smaller than requested.
  Always read the returned `risk_check`/`risk_score`, don't assume the full qty filled.
- `emerald_orders_halt` trips the kill switch for the whole server; nothing submits
  until `emerald_orders_resume`.
- Live mode applies stricter checks and touches real money — confirm the active mode
  with `emerald_risk_status` or `emerald_exchange_exchanges` before submitting.
- Kelly sizes run in the engine; an unreachable engine returns its error payload.

## Related
- `emerald-exchange-market-data` — get the quote/marks to price an order.
- `emerald-exchange-kg-ingestion` — record executed trades + resulting positions in the KG.
