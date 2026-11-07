# CONN-EMERALD-EXCHANGE-X402 — Quickstart

The shortest path that shows the served behaviour working.

- `CONN-EMERALD-EXCHANGE-X402-R001`: run `pytest tests/test_x402_model.py::test_intent_resource_pricing_models`.
- `CONN-EMERALD-EXCHANGE-X402-R002`: run `pytest tests/test_x402_pay_retry.py::test_pay_and_retry_loop`.
- `CONN-EMERALD-EXCHANGE-X402-R003`: run `pytest tests/test_x402_skill.py::test_coinbase_skill_reference_not_vendored`.
- `CONN-EMERALD-EXCHANGE-X402-R004`: run `pytest tests/test_x402_rusd.py::test_rusd_settlement`.
- `CONN-EMERALD-EXCHANGE-X402-R008.1`: run `pytest tests/test_payments_wallet_tools.py::test_one_typed_tool_per_wallet_operation`.
- `CONN-EMERALD-EXCHANGE-X402-R010.1`: run `pytest tests/test_payments_wallet_governor.py::test_wallet_limits_halt_breaker_and_approval`.
- `CONN-EMERALD-EXCHANGE-X402-R011.1`: run `pytest tests/test_payments_wallet_custody.py::test_wallet_secrets_resolve_only_from_references`.
- `CONN-EMERALD-EXCHANGE-X402-R012.1`: run `pytest tests/test_payments_wallet_image.py::test_runtime_bundle_is_pinned_and_absent_runtime_refuses`.
- `CONN-EMERALD-EXCHANGE-X402-R015`: run `pytest tests/test_unified_order_surface.py::test_place_routes_by_venue_and_lists_one_ledger`.
