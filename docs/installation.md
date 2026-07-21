# Installation

`emerald-exchange` is a standard Python package and a prebuilt container image.
Pick the path that matches how you want to run it.

## Requirements

- **Python 3.11–3.14** (matches `requires-python = ">=3.11,<3.15"` in `pyproject.toml`).
- No external service is required to start: the default **Paper** backend is fully
  self-contained, and every live exchange or data connector remains inactive when
  its credentials are absent.

## From PyPI (recommended)

```bash
pip install emerald-exchange
```

### Optional extras

The base install ships the core MCP server and the Paper backend. Install the
extra for the venues and data providers you need:

| Extra | Install | Pulls in |
|---|---|---|
| `alpaca` | `pip install "emerald-exchange[alpaca]"` | Alpaca equities + crypto (`alpaca-py`) |
| `crypto` | `pip install "emerald-exchange[crypto]"` | CCXT multi-exchange crypto (`ccxt`) |
| `binance` | `pip install "emerald-exchange[binance]"` | Binance client (`python-binance`) |
| `prediction_markets` | `pip install "emerald-exchange[prediction_markets]"` | Kalshi + Polymarket (`kalshi-python`, `py-clob-client`, `websockets`, `httpx`) |
| `fundamentals` | `pip install "emerald-exchange[fundamentals]"` | SEC EDGAR fundamentals (`edgartools`) |
| `wallet_intel` | `pip install "emerald-exchange[wallet_intel]"` | Polymarket wallet analytics (`polars`, `py-clob-client`) |
| `agent` | `pip install "emerald-exchange[agent]"` | Pydantic-AI A2A agent + Logfire tracing |
| `all` | `pip install "emerald-exchange[all]"` | Every backend and data provider |

```bash
# Typical: run the MCP server with crypto + prediction-market venues
pip install "emerald-exchange[crypto,prediction_markets]"
```

## From source

```bash
git clone https://github.com/Knuckles-Team/emerald-exchange.git
cd emerald-exchange
pip install -e ".[all]"          # editable install with every extra
```

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv pip install -e ".[all]"
uv run emerald-exchange-mcp
```

## Prebuilt Docker image

A multi-stage, slim runtime image (non-root, least-privilege) is published on every
release (entrypoint `emerald-exchange-mcp`):

```bash
docker pull knucklessg1/emerald-exchange:latest

docker run --rm -i \
  knucklessg1/emerald-exchange:latest        # stdio transport (default)
```

For a pinned, reproducible pull, reference the release digest instead of the
mutable `:latest` tag (see the [Deployment](deployment.md) guide for the
least-privilege `docker run` flags):

```bash
docker pull knucklessg1/emerald-exchange@sha256:<digest>
```

For an HTTP server with a published port — and the companion A2A agent server —
see [Deployment](deployment.md).

## Verify the install

```bash
emerald-exchange-mcp --help
python -c "import emerald_exchange; print(emerald_exchange.__version__)"
```

## Next steps

- **[Deployment](deployment.md)** — run it as a long-lived MCP server and agent server behind Caddy + DNS.
- **[Usage](usage.md)** — call the tools, the Python API, and the cockpit CLI.
- **[Configuration schema](config_schema.md)** — the `trading` config block and the backend matrix.
