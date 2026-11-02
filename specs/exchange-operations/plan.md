# EMERALD-OPS — Implementation plan

Governing spec: [spec.md](spec.md). Rows: [requirements.md](requirements.md).

## Summary

This plan delivers exchange read operations for the connector, reusing the SDK for shared capabilities.

## Technical Context

- **Language/Version**: Python 3.14 (floor 3.12)
- **Primary Dependencies**: scion-sdk, fastmcp
- **Storage**: N/A; the connector stores nothing
- **Testing**: pytest; the proof level each row names
- **Target Platform**: Linux containers
- **Project Type**: connector (MCP server)
- **Performance Goals**: N/A
- **Constraints**: one tool per API operation; shared capabilities come from the SDK
- **Scale/Scope**: 14 rows

## Constitution Check

- One owner per concept: pass. The connector owns one external system's calls, mappings and tools only.
- Connectors depend on the SDK and are called through arbora: pass.
- No ratchets: pass. The rows add no suppression.

## Project Structure

```text
pyproject.toml  existing
emerald_exchange/ontology/quant.ttl  existing
emerald_exchange/mcp/mcp_orders.py  existing
emerald_exchange/analyses.py  existing
emerald_exchange/mcp/mcp_debate.py  existing
emerald_exchange/mcp_server.py  existing
emerald_exchange/risk_guards.py  existing
```

## Phase 0: Research

No unknowns. Each row names the code it touches.

## Phase 1: Design

### Multi-asset provider sources

Extend the read facade with bounded, non-authoritative provider source reads for
FX, commodity spot and specific futures prices, and dated property valuations.
Provider credentials come from the operator environment and never tool arguments.
Prices retain source time and instrument identity; a fixed futures contract has
an explicit no-roll policy and provider expiry. Property valuations retain the
provider date and report age against a caller-selected freshness threshold.
Synthetic provider fixtures establish transport behavior, not live entitlements.

Twelve Data's XAU/USD quote provides a documented gold spot observation. Its
last quote timestamp identifies a minute candle, not a tick. Keep that time
basis explicit and do not assert live entitlements from offline fixtures.

The account source proof also exercises the SDK account-bound validator. It
replays account, position and CSV records into a real graph. This evidence uses
synthetic provider responses and does not establish live account access.

The stock provider proof also runs the SDK stock adapter with the served pack.
It replays bars, quotes, news, dividends and company records into a real graph.
Provider responses are synthetic and do not establish live data rights.

## Phase 2: Task approach

`tasks.md` holds one task line per row, producer first.

## Complexity Tracking

None. The constitution check passed.

## Build contract

The repository pre-commit hooks apply: `ruff-format`, `connector-standard`, `secrets`, `tests-fast`. Each row names its proving test. No suppression and no duplicate implementation.

## Production caller chain

1. `EMERALD-OPS-R001`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> scion_sdk.mcp.tool_surface.register_tool_surface(verbose_targets=ExchangeReadOperations) at mcp_server.py:131 -> emerald_exchange/exchange_operations.py::ExchangeReadOperations -> ExchangeBackend method in emerald_exchange/backends.py.
2. `EMERALD-OPS-R002`: scion_sdk connector discovery reads the scion_sdk.connector entry point in pyproject.toml (emerald-exchange-mcp = emerald_exchange.mcp_server:mcp_server) -> emerald_exchange/mcp_server.py::get_mcp_instance names the server and content pack.
3. `EMERALD-OPS-R003`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> register_tool_surface at mcp_server.py:131 -> tool emerald_exchange_get_account -> emerald_exchange/exchange_operations.py::ExchangeReadOperations.get_account -> emerald_exchange/backends.py Alpaca backend account read (_finite_alpaca_value at backends.py:246).
4. `EMERALD-OPS-R004`: arbora fleet call -> tool emerald_exchange_get_account_snapshot (emerald_exchange/connector_sources.py:190) -> emerald_exchange/exchange_operations.py::ExchangeReadOperations.get_account_snapshot (line 102) -> Alpaca backend account and positions reads.
5. `EMERALD-OPS-R005`: (planned) arbora FleetFinanceReadPort -> fleet call -> nine new tools emerald_exchange_list_markets and siblings -> ExchangeReadOperations (exchange_operations.py:53) -> new emerald_exchange/prediction_markets.py::PredictionMarketReader and ExchangeBackend.list_orders; today only mcp_prediction_markets.py::register_prediction_market_tools serves fetch actions.
6. `EMERALD-OPS-R006`: (planned) console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> register_order_tools (mcp_orders.py:12) -> served emerald_orders submit action (today tool name emerald_orders_submit) -> new receipt check before backend.submit_order; the existing guard is risk_guard.pre_trade_check.
7. `EMERALD-OPS-R007`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> serve_analytic_actions (analytic_tools.py) -> emerald_statarb tools -> emerald_exchange/analyses.py::ou_stat_arb_signal (line 128) and dynamic_beta_hedge (line 93) -> emerald_exchange/_engine.py::run_analysis (line 73); quant.ttl still carries the fin:servedBy kernels to be rebound.
8. `EMERALD-OPS-R008`: (planned) console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> register_order_tools (mcp_orders.py:12) -> emerald_orders submit -> new OrderAdmissionReceipt digest check -> backend.submit_order; today only risk_guard.pre_trade_check gates the submit.
9. `EMERALD-OPS-R009`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> serve_analytic_actions -> tool emerald_signals (emerald_exchange/mcp/mcp_signals.py:83) -> (planned) new actions pattern_classify and profit_attribution -> new wrappers in emerald_exchange/analyses.py -> scion_sdk/compute/finance.py (planned, SCION-FINANCE-SOURCES-R904).
10. `EMERALD-OPS-R010`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> serve_analytic_actions -> tool emerald_debate (emerald_exchange/mcp/mcp_debate.py:17) and (planned) new emerald_journal -> scion_sdk/finance/research_records.py::ResearchRecordSink (planned, SCION-FINANCE-SOURCES-R903); emerald_journal is added to the registrars list (mcp_server.py:102).
11. `EMERALD-OPS-R011`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> serve_analytic_actions -> tool emerald_risk kelly (emerald_exchange/mcp/mcp_risk.py::_dispatch, line 72, kelly branch line 120) -> today RiskGuard.kelly_criterion (risk_guards.py:309); (planned) analyses.py::position_size -> _engine.py::run_analysis.
12. `EMERALD-OPS-R012`: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> serve_analytic_actions -> tool emerald_signals (mcp_signals.py:83) -> (planned) action distribution_shift -> emerald_exchange/analyses.py::distribution_shift (line 338, currently refuse) -> _engine.py::run_analysis.
13. `EMERALD-OPS-R013`: (planned) console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> new banking entry in the registrars list (mcp_server.py:102) -> emerald_exchange/mcp/mcp_banking.py::emerald_banking -> emerald_exchange/analyses.py wrappers -> scion_sdk/compute/finance.py (planned, SCION-FINANCE-SOURCES-R904); banking.ttl already ships in emerald_exchange/ontology.
14. `EMERALD-OPS-R014`: (planned) arbora finance.wallet_operation -> fleet call -> new tool wallet_operation_apply (registered in the registrars list at mcp_server.py:102) -> scion_sdk.writeback_sinks.core.run_writeback with ops wallet_envelope -> venue call inside the sink.

## Cross-repo seams

none. The cited owner rows are library capabilities the connector calls in process; spec.md names them.
