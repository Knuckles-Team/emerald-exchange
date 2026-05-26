# Concept Registry — emerald-exchange

> **Prefix**: `CONCEPT:EE-*`
> **Version**: 0.1.0
> **Bridge**: [`CONCEPT:ECO-4.0`](../../agent-utilities/docs/concepts.md) (Unified Toolkit Ingestion)

---

## Project-Specific Concepts

| Concept ID | Name | Description |
|------------|------|-------------|
| `CONCEPT:EE-001` | MCP Server | MCP entrypoint — action-routed finance tools with config.json backend resolution |
| `CONCEPT:EE-002` | Exchange Backend Protocol | Abstract `ExchangeBackend` protocol with factory registry pattern |
| `CONCEPT:EE-003` | Paper Backend | Full simulation backend — default for all new installations |
| `CONCEPT:EE-004` | Alpaca Backend | Alpaca Markets integration (equities + crypto, FREE paper trading) |
| `CONCEPT:EE-005` | CCXT Backend | CCXT multi-exchange crypto support (Binance, Coinbase, Kraken, 100+) |
| `CONCEPT:EE-006` | Freqtrade Backend | Freqtrade REST API strategy execution backend |
| `CONCEPT:EE-007` | Risk Guards | Pre-trade risk validation, circuit breakers, kill switch (OS-5.1) |
| `CONCEPT:EE-008` | Market Data Tools | MCP tool domain `market_data` — quote, historical, exchanges |
| `CONCEPT:EE-009` | Order Management Tools | MCP tool domain `orders` — submit, cancel, status, halt, resume |
| `CONCEPT:EE-010` | Portfolio Tools | MCP tool domain `portfolio` — positions, account |
| `CONCEPT:EE-011` | Risk Management Tools | MCP tool domain `risk` — drawdown_check, daily_loss_check, kelly, limits |
| `CONCEPT:EE-012` | Signal Generation Tools | MCP tool domain `signals` — regime, alpha, fuse |
| `CONCEPT:EE-013` | Strategy Management Tools | MCP tool domain `strategy` — list, promote, export |
| `CONCEPT:EE-014` | Trading Mode Enum | Paper/Live mode gating with config-driven default |
| `CONCEPT:EE-015` | Kelly Criterion Sizing | Half-Kelly position sizing capped at configurable max_position_pct |
| `CONCEPT:EE-016` | Circuit Breaker Engine | Drawdown + daily loss + regime shift auto-halt system |
| `CONCEPT:EE-017` | Kill Switch | Emergency halt/resume lifecycle for all trading activity |
| `CONCEPT:EE-018` | Crypto-Native Analytics | `crypto` MCP domain: funding rates, whale alerts, arb scan via CCXT |
| `CONCEPT:EE-019` | Trading Debate Engine | `debate` MCP domain: multi-agent bull/bear debate with risk veto |
| `CONCEPT:EE-020` | A2A Server Integration | Native agent-to-agent interface via `agent_server.py` |

## Cross-Project References (from agent-utilities)

| Concept ID | Name | Origin |
|------------|------|--------|
| `CONCEPT:ECO-4.0` | Unified Toolkit Ingestion | agent-utilities |
| `CONCEPT:ORCH-1.2` | Confidence-Gated Router | agent-utilities |
| `CONCEPT:OS-5.1` | Prompt Injection Defense / Financial Hardening | agent-utilities |
| `CONCEPT:OS-5.2` | Cognitive Scheduler | agent-utilities |
| `CONCEPT:OS-5.3` | Guardrail Engine | agent-utilities |
| `CONCEPT:OS-5.4` | Audit Logging | agent-utilities |
| `CONCEPT:KG-2.0` | Knowledge Graph Core | agent-utilities |
| `CONCEPT:KG-2.6` | Finance Domain | agent-utilities |

## Synergy with agent-utilities

This project integrates with `agent-utilities` via `CONCEPT:ECO-4.0` (Unified Toolkit Ingestion). The `emerald_exchange` MCP server registers its tools with the agent-utilities FastMCP middleware, enabling automatic discovery, telemetry, and Knowledge Graph ingestion of all EE-* concepts.

**Finance Domain Integration**:
- Signal generation routes to `agent_utilities.domains.finance` (regime_detector, alpha_factors, signal_fusion)
- Strategy lifecycle uses `agent_utilities.domains.finance.strategy_engine`
- Heavy compute (qlib backtest, model training) routes to `data-science-mcp`
- Risk monitoring integrates with KG-native cron scheduling
