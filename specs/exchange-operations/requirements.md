# EMERALD-OPS requirements

Every requirement this specification owns, with the proof that closes it. Delivery state and
public evidence for each ID are recorded in [`status.json`](status.json); this file defines what
each ID means. The design is in [`spec.md`](spec.md) and [`plan.md`](plan.md), the test contract
in [`test-spec.md`](test-spec.md), and the work order in [`tasks.md`](tasks.md).

| ID | Requirement | Verification |
|---|---|---|
| `EMERALD-OPS-R001` | **Read-only exchange operations are per-operation tools.** Quotes, history, positions, account, order status and the `exchanges` listing (available backends, active backend, mode) are each served as one typed tool, and no write operation is served unguarded. | `tests/test_order_guard.py` |
