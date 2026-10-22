# EMERALD-OPS — Test specification

| Case | Fixture/action | Expected result |
| --- | --- | --- |
| OPS-T1 | Inspect the public methods of `ExchangeReadOperations` | Exactly `READ_OPERATIONS`; none is a write operation |
| OPS-T2 | Build the server and list tools | `emerald_exchange_exchanges` is served; no unguarded order tool is served |
| OPS-T3 | Call `exchanges` with a stub backend | Returns the registry names, the active backend and its mode |

Proof: `tests/test_order_guard.py::test_per_operation_surface_is_read_only`, `::test_no_unguarded_order_tool_is_served`, `::test_exchanges_info_operation_is_served_and_read_only`, `::test_exchanges_reports_backends_active_and_mode`.
