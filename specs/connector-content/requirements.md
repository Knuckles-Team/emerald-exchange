# CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT — Requirements

Governing spec: [spec.md](spec.md).

Each row is one requirement. A row names the file it touches and the test that proves it. The generator sets each row's state in `status.json`.

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R001` | **Default content.** `pyproject.toml` declares `emerald-exchange-mcp` as the single `scion_sdk.connector` entry point. The server lists the packaged `skill://` and `ontology://` resources and the packaged prompts with no `content=` argument. Proving test: `tests/test_default_content_surfaces.py`. | `resources/list` includes `skill://` and `ontology://`; `prompts/list` includes each packaged prompt. |
| `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R002` | **Serve the chain trade log tool.** Subsystem: connector. Caller: `emerald_exchange/mcp_server.py` → `register_tool_surface` → tool `chain_trades(chain_id, contract_id, from_block, to_block)`. The tool calls the configured node endpoint through governed HTTP and returns `EvmTrade` values via `decode_trade_log`. Config key `EMERALD_CHAIN_RPC_URL`; no default, and a missing key skips registration. Refusals: reuse SCION-SOURCE-INGEST-R005.16. Writes: none. Depends on: SCION-SOURCE-INGEST-R005.15. | Test: `tests/test_chain_trades_served.py::test_tool_decodes_logs_from_local_rpc` (L3) calls the tool against a local JSON-RPC server. |
