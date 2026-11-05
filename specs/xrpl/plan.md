# CONN-EMERALD-EXCHANGE-XRPL — Implementation plan

Governing spec: [spec.md](spec.md). Rows: [requirements.md](requirements.md).

## Summary

`emerald_exchange/mcp/` serves the MCP surface under the `emerald-exchange-mcp` connector identity declared in `pyproject.toml`. `emerald_exchange/skills/` holds the skill packages, `emerald_exchange/prompts/` the prompts, and `emerald_exchange/ontology/` the TTL packs with `certification.json`. The existing risk guard, execution bridge and paper default carry over unchanged; XRPL joins them as a new backend, not a second path. A new `emerald_exchange/` module owns the XRPL backend: wallet lifecycle, transaction build and ledger access. Wallet secrets stay behind an address reference. Signing runs preview, then scoped auto-sign or explicit approval, then submit. One attribution helper stamps SourceTag and Memo on every agent transaction. The spending-limit check and the kill-switch sit in the existing risk guard before any outbound call. The ledger client supplies fee schedules, network endpoints and live status to the resource surface.

## Technical Context

- **Language/Version**: Python 3.14 (floor 3.12)
- **Primary Dependencies**: scion-sdk, fastmcp
- **Storage**: N/A; the connector stores nothing
- **Testing**: pytest; the proof level each row names
- **Target Platform**: Linux containers
- **Project Type**: connector (MCP server)
- **Performance Goals**: N/A
- **Constraints**: one tool per API operation; shared capabilities come from the SDK
- **Scale/Scope**: 13 rows

## Constitution Check

- One owner per concept: pass. The connector owns one external system's calls, mappings and tools only.
- Connectors depend on the SDK and are called through arbora: pass.
- No ratchets: pass. The rows add no suppression.

## Project Structure

```text
emerald_exchange/mcp_server.py  existing
emerald_exchange/risk_guards.py  existing
emerald_exchange/prompts/__init__.py  existing
emerald_exchange/skills/__init__.py  existing
emerald_exchange/ontology/migrations/manifest.json  existing
```

## Phase 0: Research

No unknowns. Each row names the code it touches.

## Phase 1: Design

### Interfaces and data model

MCP tools follow the existing per-operation pattern: `xrpl_wallet_*`, `xrpl_pay_*`, `xrpl_trust_*`, `xrpl_escrow_*`, `xrpl_dex_*`, `xrpl_account_*`. Each mutating tool returns a preview object carrying fee, destination, attribution and limit-check result before it signs. The resource surface adds docs, network endpoint, fee schedule and live status entries. The ontology content lands as a new XRPL TTL in `emerald_exchange/ontology/` under the existing certification.

### Live integration path

MCP tool call, XRPL backend, ledger client, signed transaction with SourceTag and Memo, ledger result. Read-only tools stop at the ledger query. No path bypasses the risk guard; the kill-switch check runs first.

### Quality and release gates

Repository pre-commit stage on changed files. `tests/test_public_specs.py` checks the spec contract. XRPL tests run against the test network or a local validator, never production.

### Risks, alternatives, and decisions

Decision: testnet default and preview-before-sign; production needs the explicit opt-in row and a dated Amendments entry. Risk: fee drift; the fee schedule resource refreshes live and the spending-limit check reads the same source. Alternative rejected: hosted signing; the key material would leave the connector boundary.

### Amendments

- None yet.

## Phase 2: Task approach

`tasks.md` holds one task line per row, producer first.

## Complexity Tracking

None. The constitution check passed.

## Build contract

The repository pre-commit hooks apply: `ruff-format`, `connector-standard`, `secrets`, `tests-fast`. Each row names its proving test. No suppression and no duplicate implementation.

## Production caller chain

1. `CONN-EMERALD-EXCHANGE-XRPL-R001`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> emerald_xrpl_wallet_create, _wallet_load, _sign -> emerald_exchange/xrpl/wallet.py::create_wallet, load_wallet, sign; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
2. `CONN-EMERALD-EXCHANGE-XRPL-R002`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> emerald_xrpl_send_xrp, _send_rlusd -> emerald_exchange/xrpl/payments.py::send_xrp, send_rlusd -> risk.check_spend -> attribution.attach -> preview; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
3. `CONN-EMERALD-EXCHANGE-XRPL-R003`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> emerald_xrpl_trust_set, _trust_raise, _trust_remove, _trust_get -> emerald_exchange/xrpl/trust_lines.py -> account.py::account_lines; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
4. `CONN-EMERALD-EXCHANGE-XRPL-R004`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> emerald_xrpl_escrow_create, _escrow_release, _escrow_refuse, _escrow_status -> emerald_exchange/xrpl/escrow.py; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
5. `CONN-EMERALD-EXCHANGE-XRPL-R005`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> emerald_xrpl_offer_create, _offer_cancel, _book_offers, _amm_swap -> emerald_exchange/xrpl/dex.py; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
6. `CONN-EMERALD-EXCHANGE-XRPL-R006`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> emerald_xrpl_account_info, _balances, _offers, _escrows -> emerald_exchange/xrpl/account.py::account_info, account_lines, account_offers, account_objects; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
7. `CONN-EMERALD-EXCHANGE-XRPL-R007`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> every mutating tool -> emerald_exchange/xrpl/attribution.py::attach; emerald_xrpl_audit_trail -> audit_trail; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
8. `CONN-EMERALD-EXCHANGE-XRPL-R008`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("xrpl", "XRPLTOOL", register_xrpl_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_xrpl.py::register_xrpl_tools -> emerald_xrpl_spend_status, emerald_xrpl_halt and payments.py -> emerald_exchange/xrpl/risk.py::check_spend; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
9. `CONN-EMERALD-EXCHANGE-XRPL-R009`: (planned) any xrpl tool -> emerald_exchange/xrpl/client.py::connect -> emerald_exchange/xrpl/safety.py::require_network, reached under the console script emerald-exchange-mcp via register_xrpl_tools.
10. `CONN-EMERALD-EXCHANGE-XRPL-R010`: (planned) mcp_server.py::get_mcp_instance calls emerald_exchange/xrpl/resources.py::register_resources on the FastMCP instance after create_mcp_server -> xrpl://docs, endpoints, fees, status.
11. `CONN-EMERALD-EXCHANGE-XRPL-R011`: (planned) ConnectorContent.for_package prompt provider (emerald_exchange/mcp_server.py:34, wired in get_mcp_instance at mcp_server.py:14) lists xrpl_payment.json, xrpl_escrow_work.json and xrpl_spending_limit_check.json from emerald_exchange/prompts through prompts/list.
12. `CONN-EMERALD-EXCHANGE-XRPL-R012`: (planned) ConnectorContent.for_package skill provider (emerald_exchange/mcp_server.py:34, wired in get_mcp_instance at mcp_server.py:14) serves three new SKILL.md directories under emerald_exchange/skills as skill:// resources.
13. `CONN-EMERALD-EXCHANGE-XRPL-R013`: (planned) ConnectorPack.Import at registration reads emerald_exchange/ontology/xrpl.ttl and the entry in emerald_exchange/ontology/migrations/manifest.json; the ontology directory already holds emerald.ttl, trading.ttl, quant.ttl and banking.ttl.

## Cross-repo seams

none
