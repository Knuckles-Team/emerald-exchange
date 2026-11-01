# CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT — Implementation plan

Governing spec: [spec.md](spec.md). Rows: [requirements.md](requirements.md).

## Summary

`pyproject.toml` declares `emerald-exchange-mcp` as the connector identity. `create_mcp_server` resolves the packaged content of `emerald_exchange` from it.

## Technical Context

- **Language/Version**: Python 3.14 (floor 3.12)
- **Primary Dependencies**: scion-sdk, fastmcp
- **Storage**: N/A; the connector stores nothing
- **Testing**: pytest; the proof level each row names
- **Target Platform**: Linux containers
- **Project Type**: connector (MCP server)
- **Performance Goals**: N/A
- **Constraints**: one tool per API operation; shared capabilities come from the SDK
- **Scale/Scope**: 2 rows

## Constitution Check

- One owner per concept: pass. The connector owns one external system's calls, mappings and tools only.
- Connectors depend on the SDK and are called through arbora: pass.
- No ratchets: pass. The rows add no suppression.

## Project Structure

```text
pyproject.toml  existing
tests/test_default_content_surfaces.py  existing
emerald_exchange/mcp_server.py  existing
```

## Phase 0: Research

No unknowns. Each row names the code it touches.

## Phase 1: Design

The rows are delivered in place; the design is the caller chain below.

## Phase 2: Task approach

`tasks.md` holds one task line per row, producer first.

## Complexity Tracking

None. The constitution check passed.

## Build contract

The repository pre-commit hooks apply: `ruff-format`, `connector-standard`, `secrets`, `tests-fast`. Each row names its proving test. No suppression and no duplicate implementation.

## Production caller chain

1. `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R001`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> scion_sdk.mcp.server.create_mcp_server(content=ConnectorContent.for_package) at mcp_server.py:14 -> packaged skills and ontology under emerald_exchange/ served as skill:// and ontology:// resources.
2. `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R002`: (planned) console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> a new registrar for the chain trade tool in the registrars list (mcp_server.py:102) -> new tool chain_trades -> scion_sdk.adapters.evm_chain EvmTrade and decode_trade_log; skipped when EMERALD_CHAIN_RPC_URL is unset.

## Cross-repo seams

none
