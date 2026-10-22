# EMERALD-OPS — Exchange read operations

**Owner:** Emerald Exchange. **Delivery:** SPECIFIED. **Acceptance:** NOT_AUDITED.

See [`requirements.md`](requirements.md) for the definition of every requirement ID this spec owns and [`status.json`](status.json) for their current delivery and acceptance state.

## Outcome

The exchange backend's read-only operations are served as one typed MCP tool each: `emerald_exchange_get_quote`, `_get_historical`, `_get_positions`, `_get_account`, `_get_order_status` and `_exchanges`. The `exchanges` operation lists the available exchange backends, the active backend and its mode, so a caller can see what the server is connected to before reading data.

## Requirements

| ID | Requirement | Evidence |
| --- | --- | --- |
| OPS-1 | Every read-only backend operation, including `exchanges`, is a per-operation tool | `tests/test_order_guard.py` |
| OPS-2 | Writes (submit, cancel, connect, disconnect) are never per-operation tools; orders go through the risk-guarded `emerald_orders_*` tools | `tests/test_order_guard.py` |

## Boundaries

State-changing operations stay behind RiskGuard limits, halts and live-mode approval (`mcp/mcp_orders.py`). `exchanges` reports configuration only and changes nothing.
