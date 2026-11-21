---
name: emerald-exchange-order-execution
skill_type: skill
description: >-
  Check the state of orders and the positions they change with `emerald_exchange_get_order_status` and
  `emerald_exchange_get_positions`. This connector is read-only: orders are placed, changed and cancelled only
  through the platform's risk-guarded order tools, which check limits, halts and live-mode approval first. Use
  when the agent must report whether an order is open, filled or rejected, with filled quantity, average price
  and fees. Do NOT use to read quotes or history (use emerald-exchange-market-data) and never route an order
  around the risk guard.
license: MIT
tags: [emerald-exchange, orders, execution, risk]
metadata:
  author: Knuckles-Team
  version: '0.2.0'
---
# Emerald Exchange Order Status

Placing, modifying or cancelling an order changes exchange state, so it goes only through the risk-guarded
order tools, never through this connector's read tools. This skill covers the read side: what happened to an
order that was already submitted.

## When to use
- Report the status of an order by id: open, filled, rejected or cancelled.
- Report filled quantity, average price and fees.
- Show the positions after a fill.

## When NOT to use
- Submit, modify or cancel an order, or halt trading: the platform's risk-guarded order tools.
- Quotes and bars: `emerald-exchange-market-data`.

## Prerequisites & environment
Connect to the **`emerald-exchange`** MCP server. The active backend and mode come from the trading
configuration and default to the paper backend, which needs no credentials. Alpaca reads need the Alpaca
credentials in the operator configuration; provider reads need their provider key. Every tool here is
read-only and typed; there is no `action` argument. Never print a key.

## Tools
| Tool | Arguments | Returns |
|---|---|---|
| `emerald_exchange_get_order_status` | `order_id` | `order_id`, `status`, `filled_qty`, `average_price`, `fees`, `exchange`, `timestamp` |
| `emerald_exchange_get_positions` | none | positions with `symbol`, `qty`, `avg_entry_price`, `unrealized_pnl` |

## Procedure
1. Read the status with the exact id the order tool returned. Never guess an id.
2. Report the status words as the exchange gives them.
3. When a fill is reported, read the positions and show the change.

## Gotchas
- A paper backend fills instantly and at simulated prices; state the mode with the result.
- Partially filled orders show `filled_qty` below the ordered quantity; do not call them filled.
