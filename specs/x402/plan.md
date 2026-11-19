# CONN-EMERALD-EXCHANGE-X402 — Implementation plan

Governing spec: [spec.md](spec.md). Rows: [requirements.md](requirements.md).

## Summary

Wallet, signing, attribution, RLUSD payment, spending limits and the kill-switch live in the XRPL spec rows of this repository. The x402 work adds only the protocol layer: the typed models, the loop, the settlement mapping, the skill reference and the prompts. No second wallet path exists. A new `emerald_exchange/` module wraps the XRPL backend. It calls the x402-enabled endpoint, reads the 402 payment requirement, settles in RLUSD through the XRPL payment path, and retries once with the payment proof. The Coinbase agentic-wallet skill content is a reference entry in the skill surface. The connector stores the reference and its freshness check; the upstream content does not ship here.

### Server-side wallet and the unified order surface (R008.1, R010.1, R011.1, R012.1, R015)

The image bundles the wallet runtime at a pinned release and checksum through the container table in `pyproject.toml`. The runtime daemon runs from the same image as its own process (`emerald-wallet-daemon`), unlocked by a password it reads on stdin, with its encrypted state seeded from a secret reference. The MCP server reaches the daemon only through the runtime CLI over the shared unix socket, authenticated by an agent credential that also resolves from references. A new `emerald_exchange/payments` package holds the custody resolver, the CLI transport, the append-only ledger, the governor and the wallet service; `mcp/mcp_payments.py` serves one typed tool per bounded runtime operation, and `mcp/mcp_orders.py` gains the venue-routed `emerald_orders_place` and `emerald_orders_list` over the same ledger. The exchange venue reuses the existing guarded submit body, extracted into `submit_exchange_order`, so the risk guard path is unchanged.

## Technical Context

- **Language/Version**: Python 3.14 (floor 3.12)
- **Primary Dependencies**: scion-sdk, fastmcp
- **Storage**: the append-only payments ledger file of R010.1 (`payments.ledger_path`); no other store
- **Testing**: pytest; the proof level each row names
- **Target Platform**: Linux containers
- **Project Type**: connector (MCP server)
- **Performance Goals**: N/A
- **Constraints**: one tool per API operation; shared capabilities come from the SDK
- **Scale/Scope**: 15 rows and 4 child rows

## Constitution Check

- One owner per concept: pass. The connector owns one external system's calls, mappings and tools only.
- Connectors depend on the SDK and are called through arbora: pass.
- No ratchets: pass. The rows add no suppression.

## Project Structure

```text
emerald_exchange/mcp_server.py  existing
emerald_exchange/mcp/mcp_orders.py  existing (submit_exchange_order, register_unified_order_tools)
emerald_exchange/mcp/mcp_payments.py  new
emerald_exchange/payments/custody.py  new
emerald_exchange/payments/daemon.py  new
emerald_exchange/payments/governor.py  new
emerald_exchange/payments/ledger.py  new
emerald_exchange/payments/service.py  new
emerald_exchange/payments/wallet_runtime.py  new
pyproject.toml  existing ([tool.pipelines.container], emerald-wallet-daemon script)
emerald_exchange/skills/__init__.py  existing
emerald_exchange/prompts/__init__.py  existing
```

## Phase 0: Research

The wallet decision is resolved in [research.md](research.md). The runtime's command line, flags and daemon arguments were read from the pinned release; no other unknowns.

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

- 2026-11-06: the owner chose the server-side bundled wallet; R008.1, R010.1, R011.1, R012.1 and R015 deliver it. Decision record in [research.md](research.md).

## Phase 2: Task approach

`tasks.md` holds one task line per row, producer first.

## Complexity Tracking

None. The constitution check passed.

## Build contract

The repository pre-commit hooks apply: `ruff-format`, `connector-standard`, `secrets`, `tests-fast`. Each row names its proving test. No suppression and no duplicate implementation.

## Production caller chain

1. `CONN-EMERALD-EXCHANGE-X402-R001`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("x402", "X402TOOL", register_x402_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_x402.py::register_x402_tools -> emerald_x402 -> emerald_exchange/x402/models.py::X402Request.model_validate; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
2. `CONN-EMERALD-EXCHANGE-X402-R002`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("x402", "X402TOOL", register_x402_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_x402.py::register_x402_tools -> emerald_x402 -> emerald_exchange/x402/client.py::fetch_paid -> scion_sdk.payments.X402PaymentClient; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
3. `CONN-EMERALD-EXCHANGE-X402-R003`: (planned) ConnectorContent.for_package skill provider (emerald_exchange/mcp_server.py:34, wired in get_mcp_instance at mcp_server.py:14) -> new emerald_exchange/x402/skill_reference.py::resolve_skill -> skill://x402-agentic-wallet, and emerald_x402 action skill_freshness registered via register_x402_tools.
4. `CONN-EMERALD-EXCHANGE-X402-R004`: (planned) console script emerald-exchange-mcp (pyproject.toml:61) -> emerald_exchange/mcp_server.py::mcp_server (mcp_server.py:160) -> get_mcp_instance (mcp_server.py:14) -> a new ("x402", "X402TOOL", register_x402_tools) tuple added to the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_x402.py::register_x402_tools -> emerald_x402 pay -> emerald_exchange/x402/settlement.py::settle_rlusd -> emerald_exchange/xrpl/payments.py::send_rlusd; the registrars list is served by emerald_exchange/analytic_tools.py::serve_analytic_actions (analytic_tools.py:91, called at mcp_server.py:150).
5. `CONN-EMERALD-EXCHANGE-X402-R005`: (planned) emerald_exchange/x402/settlement.py -> emerald_exchange/xrpl/wallet.py::load_wallet and sign, reached from emerald_x402 pay (register_x402_tools) under the console script emerald-exchange-mcp.
6. `CONN-EMERALD-EXCHANGE-X402-R006`: (planned) emerald_x402 pay -> emerald_exchange/x402/client.py::fetch_paid -> emerald_exchange/xrpl/attribution.py::attach -> emerald_exchange/xrpl/risk.py::check_spend before signing.
7. `CONN-EMERALD-EXCHANGE-X402-R007`: (planned) ConnectorContent.for_package prompt provider (emerald_exchange/mcp_server.py:34, wired in get_mcp_instance at mcp_server.py:14) lists emerald_exchange/prompts/x402_purchase.json and x402_spending_limit_check.json through prompts/list; the prompts directory exists with only __init__.py today.

8. `CONN-EMERALD-EXCHANGE-X402-R008.1`: console script emerald-exchange-mcp -> emerald_exchange/mcp_server.py::get_mcp_instance -> registrars entry ("payments", "PAYMENTSTOOL") -> analytic_tools.py::serve_analytic_actions -> mcp/mcp_payments.py::register_payments_tools -> payments/service.py::WalletService -> payments/wallet_runtime.py::WalletRuntime -> runtime CLI subprocess.
9. `CONN-EMERALD-EXCHANGE-X402-R010.1`: WalletService.send -> payments/governor.py::PaymentGovernor.admit -> risk_guards.py::RiskGuard.is_halted and payments/ledger.py::PaymentLedger.spent_since.
10. `CONN-EMERALD-EXCHANGE-X402-R011.1`: console script emerald-wallet-daemon -> payments/daemon.py::main -> build_daemon_launch -> payments/custody.py::resolve_daemon_material -> os.execve of the runtime daemon; and WalletService -> custody.py::resolve_agent_credential.
11. `CONN-EMERALD-EXCHANGE-X402-R012.1`: release pipeline renders the Dockerfile from `[tool.pipelines.container]` -> image build stage downloads and checks the pinned runtime archive -> WalletRuntime runs `payments.runtime.bin`.
12. `CONN-EMERALD-EXCHANGE-X402-R015`: registrars entry ("order_surface", "ORDERTOOL") -> mcp/mcp_orders.py::register_unified_order_tools -> emerald_orders_place -> submit_exchange_order (exchange) or WalletService.send (wallet) -> PaymentLedger.append; emerald_orders_list -> PaymentLedger.records.

## Cross-repo seams

none
