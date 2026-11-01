# CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R001` | `tests/test_default_content_surfaces.py` | The listings include the packaged skills, ontology and prompts. |

## Rows awaiting bound tests
- `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R002`: planned proof `tests/test_chain_trades_served.py::test_tool_decodes_logs_from_local_rpc`. Expected: With EMERALD_CHAIN_RPC_URL pointing at a local JSON-RPC server, chain_trades returns decoded EvmTrade values for the block range.. Refusal: With the key unset the tool is not registered; an RPC error returns the SCION-SOURCE-INGEST-R005.16 refusal and no trades..
