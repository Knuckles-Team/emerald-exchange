# emerald-exchange

Unified Finance **MCP Server + A2A Agent** for the agent-utilities ecosystem —
fully abstracted exchange backends for equities, crypto, derivatives, and
prediction markets, with pre-trade financial hardening.

!!! info "Official documentation"
    This site is the canonical reference for `emerald-exchange`, maintained
    alongside every release.

[![PyPI](https://img.shields.io/pypi/v/emerald-exchange)](https://pypi.org/project/emerald-exchange/)
![MCP Server](https://badge.mcpx.dev?type=server 'MCP Server')
[![License](https://img.shields.io/pypi/l/emerald-exchange)](https://github.com/Knuckles-Team/emerald-exchange/blob/main/LICENSE)
[![GitHub](https://img.shields.io/badge/source-GitHub-181717?logo=github)](https://github.com/Knuckles-Team/emerald-exchange)

## Overview

`emerald-exchange` is a single multi-asset finance hub that exposes execution,
market data, risk, signals, fundamentals, and wallet intelligence as typed,
action-routed MCP tools. Every order is validated by a pre-trade risk guard
(OS-5.1 financial hardening) before it reaches an exchange backend. It provides:

- **Five exchange backends** — Paper (the always-on default), Alpaca, CCXT
  (Binance / Coinbase / Kraken and 100+ venues), Freqtrade, and Polymarket — all
  behind one `ExchangeBackend` protocol.
- **Action-routed MCP tool domains** — market data, orders, portfolio, risk,
  signals, strategy, crypto, derivatives, market-making, statistical arbitrage,
  prediction markets, fundamentals (SEC EDGAR), and wallet intelligence.
- **Financial hardening** — paper-first default, Kelly-criterion position
  sizing, circuit breakers, regime-shift detection, and an instant kill switch.

Two operating invariants: trading **defaults to paper and never to live**, and
all **quant compute is delegated to the Rust epistemic-graph engine** rather than
re-implemented in Python.

## Explore the documentation

<div class="grid cards" markdown>

- :material-rocket-launch: **[Installation](installation.md)** — pip, source, extras, and the prebuilt Docker image.
- :material-server-network: **[Deployment](deployment.md)** — run the MCP and agent servers, Docker Compose, Caddy + Technitium.
- :material-console: **[Usage](usage.md)** — the MCP tools, the Python API, and the cockpit CLI.
- :material-sitemap: **[Overview](overview.md)** — enterprise features, tool surface, and architecture.
- :material-cog: **[Configuration schema](config_schema.md)** — the `trading` config block and backend matrix.
- :material-tag-multiple: **[Concepts](concepts.md)** — the `CONCEPT:EE-*` registry.

</div>

## Quick start

```bash
pip install emerald-exchange
emerald-exchange-mcp                 # stdio MCP server (default transport)
```

Run it as a network server with a published port:

```bash
emerald-exchange-mcp --transport streamable-http --host 0.0.0.0 --port 8100
```

See **[Installation](installation.md)** and **[Deployment](deployment.md)** for the
full matrix (PyPI extras, Docker image, every transport, the A2A agent server,
reverse proxy, and DNS).
