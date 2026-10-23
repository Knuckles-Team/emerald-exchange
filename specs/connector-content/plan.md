# CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT — Design and implementation plan

Governing spec: [spec.md](spec.md).

## Architecture

`pyproject.toml` declares `emerald-exchange-mcp` as the connector identity. `create_mcp_server` resolves the packaged content of `emerald_exchange` from it.
