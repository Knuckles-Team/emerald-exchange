# Emerald Exchange Documentation

> **Package**: `emerald-exchange`
> **Version**: 0.1.0
> **Concept Prefix**: `CONCEPT:EE-*`

## Documentation Index

| Document | Description |
|----------|-------------|
| [Overview](overview.md) | Technical overview, enterprise features, architecture |
| [Concepts](concepts.md) | Concept ID registry with `CONCEPT:EE-*` prefix |

## Quick Links

- [Exchange Backends](../emerald_exchange/backends.py) — Protocol + 5 implementations
- [Risk Guards](../emerald_exchange/risk_guards.py) — OS-5.1 financial hardening
- [MCP Server](../emerald_exchange/mcp_server.py) — Entry point
- [MCP Market Data](../emerald_exchange/mcp/mcp_market_data.py) — Quote, historical
- [MCP Orders](../emerald_exchange/mcp/mcp_orders.py) — Submit, cancel, halt
- [MCP Portfolio](../emerald_exchange/mcp/mcp_portfolio.py) — Positions, account
- [MCP Risk](../emerald_exchange/mcp/mcp_risk.py) — Drawdown, Kelly, limits
- [MCP Signals](../emerald_exchange/mcp/mcp_signals.py) — Regime, alpha, fusion
- [MCP Strategy](../emerald_exchange/mcp/mcp_strategy.py) — List, promote, export
