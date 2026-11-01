# EMERALD-OPS — Quickstart

The shortest path that shows the served behaviour working.

- `EMERALD-OPS-R001`: run `pytest tests/test_order_guard.py::test_per_operation_surface_is_read_only`.
- `EMERALD-OPS-R003`: run `pytest tests/test_alpaca_account_integrity.py`.
- `EMERALD-OPS-R005`: run `pytest tests/test_market_read_tools_served.py::test_nine_read_tools_return_provider_records`.
- `EMERALD-OPS-R006`: run `pytest tests/test_order_confirmation_receipt.py::test_order_refused_without_confirmation_receipt`.
- `EMERALD-OPS-R007`: run `pytest tests/test_quant_bindings.py::test_every_kernel_binding_uses_numeric_evaluate`.
- `EMERALD-OPS-R008`: run `pytest tests/test_order_admission.py::test_order_refused_without_receipt`.
- `EMERALD-OPS-R009`: run `pytest tests/test_research_kernels_served.py::test_signal_actions_reach_engine_methods`.
- `EMERALD-OPS-R010`: run `pytest tests/test_research_records_served.py::test_debate_and_card_tools_write_through_the_sink`.
- `EMERALD-OPS-R011`: run `pytest tests/test_position_size_served.py::test_kelly_action_returns_engine_value_and_refuses_without_engine`.
- `EMERALD-OPS-R012`: run `pytest tests/test_distribution_shift_served.py::test_shift_action_reaches_engine_method`.
- `EMERALD-OPS-R013`: run `pytest tests/test_banking_served.py::test_each_action_reaches_its_engine_method`.
- `EMERALD-OPS-R014`: run `pytest tests/test_wallet_operation_served.py::test_tool_passes_envelope_and_refuses_without_proof`.
