# emerald-exchange — Concept Overview

> **Category**: Finance | **Ecosystem Role**: MCP Server + A2A Agent
> Built on [`agent-utilities`](https://github.com/Knuckles-Team/agent-utilities) — the unified AGI Harness.

## Description

Unified Finance MCP Server providing fully abstracted exchange backends for equities,
crypto, and derivatives trading. All trading operations go through pre-trade risk validation
(OS-5.1 financial hardening) before reaching exchange backends.

## Enterprise Readiness

All agents in the ecosystem inherit enterprise-grade infrastructure from `agent-utilities`:

| Feature | Status | Source |
|:--------|:-------|:-------|
| **JWT/OIDC Authentication** | ✅ Built-in | `agent-utilities[auth]` — Authlib JWKS + API key middleware |
| **OpenTelemetry Instrumentation** | ✅ Built-in | `agent-utilities[logfire]` — OTLP export, FastAPI auto-instrumentation |
| **HashiCorp Vault Integration** | ✅ Built-in | `agent-utilities[vault]` — `secret://`, `env://`, `vault://` URI schemes |
| **Audit Logging** | ✅ Built-in | Append-only compliance trail with 30+ action types (CONCEPT:AU-OS.governance.wasm-micro-agent-sandbox) |
| **Token Usage Analytics** | ✅ Built-in | 4-bucket tracking with budget alerting (CONCEPT:AU-OS.governance.wasm-micro-agent-sandbox) |
| **Prompt Injection Defense** | ✅ Built-in | 25+ pattern scanner + jailbreak taxonomy (CONCEPT:AU-OS.config.secrets-authentication) |
| **Guardrail Engine** | ✅ Built-in | Input/output interception with block/redact/warn (CONCEPT:AU-OS.governance.reactive-multi-axis-budget) |
| **Action Execution Pipeline** | ✅ Built-in | Token, cost, duration, and node transition limits (CONCEPT:AU-ORCH.adapter.kg-graph-materialization) |
| **Resource Scheduling** | ✅ Built-in | Priority queuing + preemption limits (CONCEPT:AU-OS.state.cognitive-scheduler-preemption) |
| **Session Concurrency** | ✅ Built-in | Enqueue/reject/interrupt/rollback (CONCEPT:AU-OS.governance.reactive-multi-axis-budget) |

## Finance-Specific Features

| Feature | Status | Source |
|:--------|:-------|:-------|
| **Pre-Trade Risk Validation** | ✅ Native | `risk_guards.py` — Kelly criterion, circuit breakers |
| **Kill Switch** | ✅ Native | `emerald_orders(action="halt")` — instant halt |
| **Multi-Exchange Backends** | ✅ Native | Paper, Alpaca, CCXT (Binance/Coinbase/Kraken), Freqtrade |
| **Regime Shift Detection** | ✅ Native | KS-test on prediction distributions |
| **Human Approval Gate** | ✅ Native | Required for live trading activation |
| **Paper-First Default** | ✅ Native | `PaperBackend` is always the default |

## Concept Registry

This project implements or inherits the following ecosystem concepts:

| Concept ID | Description | Source |
|:-----------|:------------|:-------|
| AU-AHE.assimilation.autonomous-trading-ecosystem | Emerald Exchange MCP Server | This project |
| EX-AHE.harness.ee | Exchange Backend Protocol | This project |
| EX-AHE.harness.ee-6 | Risk Guards (OS-5.1) | This project |
| EX-AHE.harness.ee-7 | Market Data Tools | This project |
| EX-AHE.harness.ee-8 | Order Management Tools | This project |
| EX-AHE.harness.ee-9 | Portfolio Tools | This project |
| AU-AHE.assimilation.skill-workflow-ingest | Risk Management Tools | This project |
| EX-AHE.harness.ee-11 | Signal Generation Tools | This project |
| AU-AHE.assimilation.trading-ecosystem-spec | Strategy Management Tools | This project |
| ECO-4.1 | MCP & Universal Skills | `agent-utilities` (inherited) |

> 📖 **Full Registry**: See [`agent-utilities/docs/overview.md`](https://github.com/Knuckles-Team/agent-utilities/blob/main/docs/overview.md) for the complete 5-Pillar concept index.

## Architecture

This project follows the standardized agent-package pattern:

```
emerald-exchange/
├── emerald_exchange/          # Source code
│   ├── __init__.py
│   ├── __main__.py            # CLI entrypoint
│   ├── agent_server.py        # A2A agent entrypoint (CONCEPT:EX-AHE.harness.ee-19)
│   ├── backends.py            # Exchange backend abstractions
│   ├── risk_guards.py         # OS-5.1 financial hardening
│   ├── mcp_server.py          # MCP server entrypoint
│   └── mcp/                   # MCP tool domains
│       ├── mcp_crypto.py      # Crypto-native analytics, funding rates (CONCEPT:EX-AHE.harness.ee-17)
│       ├── mcp_debate.py      # Bull/bear trading debate engine (CONCEPT:EX-AHE.harness.ee-18)
│       ├── mcp_market_data.py # Quote, historical, exchanges
│       ├── mcp_orders.py      # Submit, cancel, halt, resume
│       ├── mcp_portfolio.py   # Positions, account
│       ├── mcp_risk.py        # Drawdown, Kelly, limits
│       ├── mcp_signals.py     # Regime, alpha, fusion
│       └── mcp_strategy.py    # List, promote, export
├── tests/                     # Test suite
├── docs/                      # Documentation
├── docker/                    # Container deployment
├── pyproject.toml             # Package metadata
└── mcp_config.json            # MCP server configuration
```

## MCP Configuration

### stdio Mode
```json
{
  "mcpServers": {
    "emerald-exchange": {
      "command": "uv",
      "args": ["run", "--with", "emerald-exchange", "emerald-exchange"],
      "env": {}
    }
  }
}
```

### Streamable HTTP Mode
```bash
emerald-exchange --transport streamable-http --port 8100
```

## Trading Agent Architecture

```mermaid
sequenceDiagram
    participant User
    participant CTO as Chief Trading Officer
    participant Quant as Quant Research Analyst
    participant Risk as Risk Compliance Officer
    participant MCP as Emerald Exchange MCP
    participant Backend as Exchange Backend

    User->>CTO: Trading hypothesis
    CTO->>Quant: Generate alpha factors
    Quant->>MCP: emerald_signals(action="alpha")
    MCP-->>Quant: Alpha factors + IC/IR scores
    Quant-->>CTO: Hypothesis with evidence
    CTO->>Risk: Pre-trade risk check
    Risk->>MCP: emerald_risk(action="kelly")
    MCP-->>Risk: Position size recommendation
    Risk-->>CTO: Approved with limits
    CTO->>MCP: emerald_orders(action="submit")
    MCP->>Backend: Execute via exchange backend
    Backend-->>MCP: Execution result
    MCP-->>CTO: Order confirmation + audit trail
```
