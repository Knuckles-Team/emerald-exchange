# AGENTS.md — emerald-exchange

> AI coding agent context for `emerald-exchange`

## Project Overview

Unified Finance MCP Server with fully abstracted exchange backends.

- **Language**: Python 3.12+
- **Framework**: FastMCP (via agent-utilities)
- **Package Manager**: uv
- **Concept Prefix**: `CONCEPT:EE-*`

## Architecture

```
emerald-exchange/
├── emerald_exchange/
│   ├── __init__.py          # Package init + version
│   ├── __main__.py          # CLI entry
│   ├── backends.py          # ExchangeBackend Protocol + 5 impls
│   ├── risk_guards.py       # OS-5.1 financial hardening
│   ├── mcp_server.py        # MCP server entry
│   └── mcp/                 # Tool domains
│       ├── mcp_market_data.py
│       ├── mcp_orders.py
│       ├── mcp_portfolio.py
│       ├── mcp_risk.py
│       ├── mcp_signals.py
│       └── mcp_strategy.py
├── tests/
│   ├── conftest.py
│   ├── test_concept_parity.py
│   ├── test_init_dynamics.py
│   └── test_startup.py
├── docs/
│   ├── index.md
│   ├── overview.md
│   └── concepts.md
└── docker/
    ├── Dockerfile
    └── compose.yml
```

## Key Commands

```bash
# Run tests
uv run pytest tests/ -v

# Run MCP server
uv run python -m emerald_exchange

# Lint
uv run ruff check emerald_exchange/

# Version bump
bump2version patch
```

## Coding Standards

- Every MCP tool must annotate its CONCEPT:EE-* ID in the docstring
- All orders must pass through `RiskGuard.pre_trade_check()` before submission
- Default backend is always `PaperBackend` — never default to live
- Use `create_backend()` factory, never instantiate backends directly in tools
- Follow `agent-utilities` patterns for `create_mcp_server()` initialization
