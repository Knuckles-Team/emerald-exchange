---
name: emerald-exchange-order-execution
description: >-
  Place, cancel, and check trading orders through the emerald-exchange MCP server
  with mandatory pre-trade risk validation, plus the emergency halt/resume kill
  switch — via the domain-typed emerald_orders tool (every order is routed through
  the risk guard). Use when the agent must submit a market/limit order, cancel or
  status an existing order by id, or halt all trading. Do NOT use to read quotes
  or positions (use emerald-exchange-market-data), and be deliberate in live mode —
  paper is the default. Do NOT bypass the risk guard with raw backend calls.
license: MIT
tags: [emerald-exchange, orders, execution, risk, trading, mcp]
metadata:
  author: Genius
  version: '0.1.0'
---
# Emerald Exchange — Order Execution

Backend-abstracted order management. **Every** order passes a pre-trade
`RiskGuard.pre_trade_check` (sizing, exposure, live-mode gating) before it reaches
the exchange, and a global kill switch can halt all trading instantly.

## When to use
- Submit a market or limit order (buy/sell) with risk validation.
- Cancel an existing order by `order_id`.
- Check the status/fill of an order by `order_id`.
- Emergency `halt` (kill switch) / `resume` of all trading.

## When NOT to use
- Reading quotes, history, positions, or account → `emerald-exchange-market-data`.
- Persisting executed trades into the KG → `emerald-exchange-kg-ingestion`.
- Market-making quoting loops, statarb, or derivatives → their dedicated emerald tools.

## Prerequisites & environment
Connect via the `mcp-client` skill against the **`emerald-exchange`** MCP server.
Mode + risk limits come from `config.json` → `trading.default_mode` (`paper`|`live`)
and `trading.risk_limits`. Default is `paper` — no credentials, simulated fills.

| Variable | Required | Notes |
|----------|----------|-------|
| (paper mode) | — | Simulated fills; safe to exercise freely |
| exchange creds (e.g. `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`) | for `live` | Real orders |

## Tools & actions
| Condensed tool | Actions |
|----------------|---------|
| `emerald_orders` | `submit`, `cancel`, `status`, `halt`, `resume` |

### Key parameters
- `symbol` + `qty` (> 0) — required for `submit`.
- `side` — `buy` or `sell` (default `buy`).
- `order_type` — `market`, `limit`, `stop`, `stop_limit` (default `market`).
- `limit_price` — required for limit/stop-limit orders.
- `order_id` — required for `cancel` and `status`.

## Recipes
Submit a limit buy:
```json
{"action": "submit", "symbol": "AAPL", "side": "buy", "qty": 10, "order_type": "limit", "limit_price": 150.0}
```
Cancel an order:
```json
{"action": "cancel", "order_id": "PAPER-000001"}
```
Emergency halt / resume:
```json
{"action": "halt"}
```

## Gotchas
- The risk guard can **reject** (`approved: false` + `reason`/`risk_score`) or **resize**
  the order — the response's `filled_qty` may be smaller than requested (`adjusted_qty`).
  Always read the returned `risk_check`/`risk_score`, don't assume the full qty filled.
- `halt` trips the kill switch for the whole server; nothing submits until `resume`.
- Live mode applies stricter checks and touches real money — confirm the active `mode`
  via `emerald_market_data action=exchanges` before submitting.
- A `limit`/`stop_limit` order with `limit_price` <= 0 is treated as a market fill in
  paper; set an explicit `limit_price`.

## Related
- `emerald-exchange-market-data` — get the quote/marks to price an order.
- `emerald-exchange-kg-ingestion` — record executed trades + resulting positions in the KG.
