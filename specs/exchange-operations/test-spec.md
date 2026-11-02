# EMERALD-OPS — Test specification

| Case | Fixture/action | Expected result |
| --- | --- | --- |
| OPS-T1 | Inspect the public methods of `ExchangeReadOperations` | Exactly `READ_OPERATIONS`; none is a write operation |
| OPS-T2 | Build the server and list tools | `emerald_exchange_exchanges` is served; no unguarded order tool is served |
| OPS-T3 | Call `exchanges` with a stub backend | Returns the registry names, the active backend and its mode |

Proof: `tests/test_order_guard.py::test_per_operation_surface_is_read_only`, `::test_no_unguarded_order_tool_is_served`, `::test_exchanges_info_operation_is_served_and_read_only`, `::test_exchanges_reports_backends_active_and_mode`.

## EMERALD-OPS-R002

`tests/test_fleet_name.py::test_connector_name_is_the_fleet_name` reads every connector name in the package. Each one is `emerald-exchange-mcp`.

## EMERALD-OPS-R003

`tests/test_alpaca_account_integrity.py` exercises the account and position provider calls, malformed account data, provider failure, and an in-process served MCP read. Provider failures must not return fabricated account or position data, and the served tool must not expose the provider exception message.

## EMERALD-OPS-R004

`tests/test_alpaca_account_integrity.py` checks the declared source and a real in-process MCP call, including provider identity, positions, and refusal when the position read fails. It also uses the SDK MCP transport and source adapter to extract the declared account record.

## Rows awaiting bound tests
- `EMERALD-OPS-R005`: planned proof `tests/test_market_read_tools_served.py::test_nine_read_tools_return_provider_records`. Expected: Each of the nine tools returns the provider records from a recorded venue response with the documented fields.. Refusal: No submit, cancel or other order call is made; a venue failure is refused without a fabricated empty list..
- `EMERALD-OPS-R006`: planned proof `tests/test_order_confirmation_receipt.py::test_order_refused_without_confirmation_receipt`. Expected: With a receipt naming the same admission digest the submit reaches the backend once against the recorded venue response.. Refusal: Without a receipt or with a different digest the tool returns ORDER_CONFIRMATION_REQUIRED and the venue is never called..
- `EMERALD-OPS-R007`: planned proof `tests/test_quant_bindings.py::test_every_kernel_binding_uses_numeric_evaluate`. Expected: Every listed kernel in quant.ttl is served by numeric.evaluate with a servedOp and emerald_statarb returns the recorded engine value.. Refusal: An unserved analysis still returns the engine_error payload from _engine.py::engine_error..
- `EMERALD-OPS-R008`: planned proof `tests/test_order_admission.py::test_order_refused_without_receipt`. Expected: A matching receipt digest lets the submit reach the recorded venue response exactly once.. Refusal: A missing or mismatched receipt returns ADMISSION_REQUIRED and the backend records zero calls..
- `EMERALD-OPS-R009`: planned proof `tests/test_research_kernels_served.py::test_signal_actions_reach_engine_methods`. Expected: Both actions return the recorded engine result for bars read from the recorded venue response.. Refusal: With no engine the actions return the refusal payload and hold no local pattern or attribution rule..
- `EMERALD-OPS-R010`: planned proof `tests/test_research_records_served.py::test_debate_and_card_tools_write_through_the_sink`. Expected: Each action writes one record through the sink and returns the record id from the recorded engine reply.. Refusal: Missing component scores or a sink refusal returns the refusal code and writes no record..
- `EMERALD-OPS-R011`: planned proof `tests/test_position_size_served.py::test_kelly_action_returns_engine_value_and_refuses_without_engine`. Expected: The kelly action returns the recorded engine value and the cap the engine applied.. Refusal: Without an engine the action is refused and no local Kelly formula remains in risk_guards.py..
- `EMERALD-OPS-R012`: planned proof `tests/test_distribution_shift_served.py::test_shift_action_reaches_engine_method`. Expected: The action returns the statistic and shifted flag from the recorded engine reply.. Refusal: Without an engine the action is refused; empty or short samples return the engine refusal code..
- `EMERALD-OPS-R013`: planned proof `tests/test_banking_served.py::test_each_action_reaches_its_engine_method`. Expected: Each of the four actions returns the recorded engine result.. Refusal: Without an engine or with invalid input the action returns the refusal code and no local value..
- `EMERALD-OPS-R014`: planned proof `tests/test_wallet_operation_served.py::test_tool_passes_envelope_and_refuses_without_proof`. Expected: A valid WalletExecutionEnvelope with proof reaches the venue once and returns the write-back attempt fields.. Refusal: Missing or failed proof returns the SDK refusal code with zero venue calls..
- `EMERALD-OPS-R001`: proof `tests/test_order_guard.py::test_per_operation_surface_is_read_only`; the test carries the row's `spec` marker when it lands.
