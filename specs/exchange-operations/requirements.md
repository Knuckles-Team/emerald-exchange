# EMERALD-OPS requirements

Every requirement this specification owns, with the proof that closes it. Delivery state and
public evidence for each ID are recorded in [`status.json`](status.json); this file defines what
each ID means. The design is in [`spec.md`](spec.md) and [`plan.md`](plan.md), the test contract
in [`test-spec.md`](test-spec.md), and the work order in [`tasks.md`](tasks.md).

| ID | Requirement | Verification |
|---|---|---|
| `EMERALD-OPS-R001` | **Read-only exchange operations are per-operation tools.** Quotes, history, positions, account, order status and the `exchanges` listing (available backends, active backend, mode) are each served as one typed tool, and no write operation is served unguarded. | `tests/test_order_guard.py` |
| `EMERALD-OPS-R002` | **Fleet name.** `pyproject.toml` declares `emerald-exchange-mcp` as the single `agent_connector_sdk.connector` entry point. The content pack, the manifest `connector`, the fingerprints and the ingest binding all carry `emerald-exchange-mcp`. Proving test: `tests/test_fleet_name.py::test_connector_name_is_the_fleet_name`. | Every connector name in the package is `emerald-exchange-mcp`. |
| `EMERALD-OPS-R003` | **Alpaca account reads retain provider identity and fail closed.** The served account read exposes the provider account ID and currency. Missing identity, invalid currency, non-finite values, or provider read failure do not produce a fabricated empty account or positions. Documented provider transport and API errors are reported without the provider message. | `tests/test_alpaca_account_integrity.py` covers the provider adapter, real in-process MCP tool, invalid responses and redacted transport failures. |
