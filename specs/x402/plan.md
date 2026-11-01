# CONN-EMERALD-EXCHANGE-X402 — Implementation plan

Governing spec: [spec.md](spec.md). Rows: [requirements.md](requirements.md).

## Summary

Wallet, signing, attribution, RLUSD payment, spending limits and the kill-switch live in the XRPL spec rows of this repository. The x402 work adds only the protocol layer: the typed models, the loop, the settlement mapping, the skill reference and the prompts. No second wallet path exists. A new `emerald_exchange/` module wraps the XRPL backend. It calls the x402-enabled endpoint, reads the 402 payment requirement, settles in RLUSD through the XRPL payment path, and retries once with the payment proof. The Coinbase agentic-wallet skill content is a reference entry in the skill surface. The connector stores the reference and its freshness check; the upstream content does not ship here.

## Technical Context

- **Language/Version**: Python 3.14 (floor 3.12)
- **Primary Dependencies**: scion-sdk, fastmcp
- **Storage**: N/A; the connector stores nothing
- **Testing**: pytest; the proof level each row names
- **Target Platform**: Linux containers
- **Project Type**: connector (MCP server)
- **Performance Goals**: N/A
- **Constraints**: one tool per API operation; shared capabilities come from the SDK
- **Scale/Scope**: 7 rows

## Constitution Check

- One owner per concept: pass. The connector owns one external system's calls, mappings and tools only.
- Connectors depend on the SDK and are called through arbora: pass.
- No ratchets: pass. The rows add no suppression.

## Project Structure

```text
emerald_exchange/mcp_server.py  existing
emerald_exchange/skills/__init__.py  existing
emerald_exchange/prompts/__init__.py  existing
```

## Phase 0: Research

No unknowns. Each row names the code it touches.

## Phase 1: Design

### Interfaces and data model

MCP tools: `x402_purchase` and `x402_status`. Models: intent, payment requirement, payment proof, settlement result. Prompts: x402 purchase, spending-limit check.

### Live integration path

`x402_purchase` calls the x402 module, which calls the XRPL payment path for the RLUSD settlement, then the ledger, then the retry with the proof. The risk guard sits on the XRPL side of the edge; x402 adds no second check.

### Quality and release gates

Repository pre-commit stage on changed files. x402 tests run against a fixture endpoint and the test network.

### Risks, alternatives, and decisions

Decision: reference the Coinbase skill content instead of vendoring it; a vendored copy drifts from upstream. Decision: settle in RLUSD through the existing XRPL path; a second wallet stack is a non-goal. Risk: upstream endpoint contract changes; the typed model fails validation instead of guessing.

### Amendments

- None yet.

## Phase 2: Task approach

`tasks.md` holds one task line per row, producer first.

## Complexity Tracking

None. The constitution check passed.

## Build contract

The repository pre-commit hooks apply: `ruff-format`, `connector-standard`, `secrets`, `tests-fast`. Each row names its proving test. No suppression and no duplicate implementation.

## Production caller chain

1. `CONN-EMERALD-EXCHANGE-X402-R001`: (planned) console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> the new registrar entry for tag x402 in the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_x402.py::register_x402_tools -> emerald_x402 -> emerald_exchange/x402/models.py::X402Request.model_validate; existing registrars are served by emerald_exchange/analytic_tools.py::serve_analytic_actions.
2. `CONN-EMERALD-EXCHANGE-X402-R002`: (planned) console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> the new registrar entry for tag x402 in the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_x402.py::register_x402_tools -> emerald_x402 -> emerald_exchange/x402/client.py::fetch_paid -> scion_sdk.payments.X402PaymentClient; existing registrars are served by emerald_exchange/analytic_tools.py::serve_analytic_actions.
3. `CONN-EMERALD-EXCHANGE-X402-R003`: (planned) ConnectorContent.for_package skill provider (emerald_exchange/mcp_server.py:14) -> new emerald_exchange/x402/skill_reference.py::resolve_skill -> skill://x402-agentic-wallet, and emerald_x402 action skill_freshness registered via register_x402_tools.
4. `CONN-EMERALD-EXCHANGE-X402-R004`: (planned) console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> the new registrar entry for tag x402 in the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_x402.py::register_x402_tools -> emerald_x402 pay -> emerald_exchange/x402/settlement.py::settle_rlusd -> emerald_exchange/xrpl/payments.py::send_rlusd; existing registrars are served by emerald_exchange/analytic_tools.py::serve_analytic_actions.
5. `CONN-EMERALD-EXCHANGE-X402-R005`: (planned) emerald_exchange/x402/settlement.py -> emerald_exchange/xrpl/wallet.py::load_wallet and sign, reached from emerald_x402 pay (register_x402_tools) under the console script emerald-exchange-mcp.
6. `CONN-EMERALD-EXCHANGE-X402-R006`: (planned) emerald_x402 pay -> emerald_exchange/x402/client.py::fetch_paid -> emerald_exchange/xrpl/attribution.py::attach -> emerald_exchange/xrpl/risk.py::check_spend before signing.
7. `CONN-EMERALD-EXCHANGE-X402-R007`: (planned) ConnectorContent.for_package prompt provider (emerald_exchange/mcp_server.py:14) lists emerald_exchange/prompts/x402_purchase.md and x402_spending_limit_check.md through prompts/list; the prompts directory exists with only __init__.py today.

## Cross-repo seams

none
