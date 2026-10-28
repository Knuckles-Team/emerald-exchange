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

`tests/test_alpaca_account_integrity.py` checks the declared source and a real in-process MCP call, including provider identity, positions, and refusal when the position read fails.
