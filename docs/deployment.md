# Deployment

<!-- BEGIN GENERATED: deployment-options -->
## Deployment Options

`emerald-exchange` exposes its MCP server (console script `emerald-exchange-mcp`) four ways. Pick the row that
matches where the server runs relative to your MCP client, then copy the matching
`mcp_config.json` below. Add the service-connection environment variables documented in the **Configuration** section.

| # | Option | Transport | Where it runs | `mcp_config.json` key |
|---|--------|-----------|---------------|------------------------|
| 1 | stdio | `stdio` | client launches a subprocess | `command` |
| 2 | Streamable-HTTP (local) | `streamable-http` | a local network port | `command` or `url` |
| 3 | Local container / uv | `stdio` or `streamable-http` | Docker / Podman / uv on this host | `command` or `url` |
| 4 | Remote URL | `streamable-http` | a remote host behind Caddy | `url` |

### 1. stdio (local subprocess)

The client launches the server over stdio via `uvx` — best for local IDEs
(Cursor, Claude Desktop, VS Code):

```json
{
  "mcpServers": {
    "emerald-exchange-mcp": {
      "command": "uvx",
      "args": ["--from", "emerald-exchange", "emerald-exchange-mcp"]
    }
  }
}
```

### 2. Streamable-HTTP (local process)

Run the server as a long-lived HTTP process:

```bash
uvx --from emerald-exchange emerald-exchange-mcp --transport streamable-http --host 0.0.0.0 --port 8000
curl -s http://localhost:8000/health        # {"status":"OK"}
```

Then either let the client launch it:

```json
{
  "mcpServers": {
    "emerald-exchange-mcp": {
      "command": "uvx",
      "args": ["--from", "emerald-exchange", "emerald-exchange-mcp", "--transport", "streamable-http", "--port", "8000"],
      "env": {
        "TRANSPORT": "streamable-http",
        "HOST": "0.0.0.0",
        "PORT": "8000"
      }
    }
  }
}
```

…or connect to the already-running process by URL:

```json
{
  "mcpServers": {
    "emerald-exchange-mcp": { "url": "http://localhost:8000/mcp" }
  }
}
```

### 3. Local container / uv

**(a) Launch a container directly from `mcp_config.json`** (stdio over the container —
no ports to manage). Swap `docker` for `podman` for a daemonless runtime:

```json
{
  "mcpServers": {
    "emerald-exchange-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "TRANSPORT=stdio",
        "knucklessg1/emerald-exchange:latest"
      ]
    }
  }
}
```

**(b) Run a local streamable-http container, then connect by URL:**

```bash
docker run -d --name emerald-exchange-mcp -p 8000:8000 \
  -e TRANSPORT=streamable-http \
  -e PORT=8000 \
  knucklessg1/emerald-exchange:latest
# or, from a clone of this repo:
docker compose -f docker/mcp.compose.yml up -d
```

```json
{
  "mcpServers": {
    "emerald-exchange-mcp": { "url": "http://localhost:8000/mcp" }
  }
}
```

**(c) From a local checkout with `uv`:**

```bash
uv run emerald-exchange-mcp --transport streamable-http --port 8000
```

### 4. Remote URL (deployed behind Caddy)

When the server is deployed remotely (e.g. as a Docker service) and published through
Caddy on the internal `*.arpa` zone, connect with the `"url"` key — no local process or
image required:

```json
{
  "mcpServers": {
    "emerald-exchange-mcp": { "url": "http://emerald-exchange-mcp.arpa/mcp" }
  }
}
```

Caddy reverse-proxies `http://emerald-exchange-mcp.arpa` to the container's `:8000`
streamable-http listener; `http://emerald-exchange-mcp.arpa/health` returns
`{"status":"OK"}` when the service is live.
<!-- END GENERATED: deployment-options -->

This page covers running `emerald-exchange` as a long-lived service: the
transports, the companion A2A agent server, a Docker Compose stack, putting it
behind a Caddy reverse proxy, and giving it a DNS name with Technitium.

`emerald-exchange` ships two console scripts: the **MCP server**
(`emerald-exchange-mcp`) and a full **A2A agent server**
(`emerald-exchange-agent`) that drives the MCP toolset through a Pydantic-AI
agent. A text-mode **cockpit** (`emerald-cockpit`) is documented in
[Usage](usage.md).

## Run the MCP server

The transport is selected with `--transport` (or the `TRANSPORT` env var):

=== "stdio (default)"

    ```bash
    emerald-exchange-mcp
    ```
    For IDE / desktop MCP clients that launch the server as a subprocess.

=== "streamable-http"

    ```bash
    emerald-exchange-mcp --transport streamable-http --host 0.0.0.0 --port 8100
    ```
    A network server with a `/health` endpoint and `/mcp` route.

=== "sse"

    ```bash
    emerald-exchange-mcp --transport sse --host 0.0.0.0 --port 8100
    ```

Health check (HTTP transports):

```bash
curl -s http://localhost:8100/health        # {"status":"OK"}
```

## Configuration (environment)

The MCP server starts with no required configuration — the default **Paper**
backend is fully self-contained. Live trading and data connectors read their own
credentials and remain inactive when those credentials are absent. The variables
most commonly set:

| Var | Default | Meaning |
|---|---|---|
| `TRANSPORT` | `stdio` | Transport: `stdio`, `streamable-http`, or `sse` |
| `HOST` | `127.0.0.1` | Bind address for HTTP transports |
| `PORT` | `8100` | Listen port for HTTP transports |
| `FUNDAMENTALSTOOL` | `True` | Register the SEC EDGAR fundamentals tool group |
| `EDGAR_IDENTITY` | — | SEC identity (`"Name email@example.com"`) for fundamentals |
| `WALLETINTELTOOL` | `True` | Register the Polymarket wallet-intelligence tool group |
| `POLY_TRADES_PATH` | — | Path to a processed Polymarket trades CSV/Parquet |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | — | Alpaca credentials (only when using Alpaca) |
| `BINANCE_API_KEY` / `BINANCE_SECRET` | — | Binance credentials (only when using Binance) |
| `COINBASE_API_KEY` / `COINBASE_SECRET` | — | Coinbase credentials (only when using Coinbase) |

All trading behavior — the default backend, default mode, risk limits, and
per-exchange settings — is configured in the `trading` block of
`~/.config/agent-utilities/config.json`. The full schema, the backend matrix, and
the complete environment-variable list are documented in the
[Configuration schema](config_schema.md).

### Backing service

`emerald-exchange` connects to **managed, SaaS exchange and data APIs** — Alpaca,
Binance, Coinbase, Kraken (via CCXT), Kalshi, Polymarket, and SEC EDGAR. These are
provider-hosted services with no local deployment, so there is no backing-system
recipe to provision: only connection configuration (API keys and identities) is
required, and the package operates entirely against the in-process Paper backend
until those credentials are supplied.

## Docker Compose

The repository ships [`docker/mcp.compose.yml`](https://github.com/Knuckles-Team/emerald-exchange/blob/main/docker/mcp.compose.yml).
It reads a sibling `.env`, publishes the HTTP MCP server on `:8100`, and starts the
companion agent server on `:9100`:

```yaml
services:
  emerald-exchange-mcp:
    image: knucklessg1/emerald-exchange:latest
    container_name: emerald-exchange-mcp
    hostname: emerald-exchange-mcp
    command: ["emerald-exchange-mcp"]
    restart: always
    env_file:
      - ../.env
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=8100
      - TRANSPORT=streamable-http
    ports:
      - "8100:8100"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

```bash
cp .env .env.local            # then edit the connector credentials you use
docker compose -f docker/mcp.compose.yml up -d
docker compose -f docker/mcp.compose.yml logs -f
```

## A2A agent server

The agent server (`emerald-exchange-agent`) launches `emerald-exchange` as a full
Pydantic-AI agent with Agent-to-Agent support, wired to the MCP toolset via
`MCP_URL`. It is defined alongside the MCP server in
[`docker/mcp.compose.yml`](https://github.com/Knuckles-Team/emerald-exchange/blob/main/docker/mcp.compose.yml)
and listens on `:9100`:

```yaml
  emerald-exchange-agent:
    image: knucklessg1/emerald-exchange:latest
    container_name: emerald-exchange-agent
    hostname: emerald-exchange-agent
    command: ["emerald-exchange-agent"]
    depends_on:
      - emerald-exchange-mcp
    restart: always
    env_file:
      - ../.env
    environment:
      - PYTHONUNBUFFERED=1
      - HOST=0.0.0.0
      - PORT=9100
      - MCP_URL=http://emerald-exchange-mcp:8100/mcp
      - PROVIDER=openai
      - LLM_BASE_URL=${LLM_BASE_URL:-http://host.docker.internal:1234/v1}
      - LLM_API_KEY=${LLM_API_KEY:-llama}
      - MODEL_ID=${MODEL_ID:-qwen/qwen3.5-9b}
      - ENABLE_WEB_UI=True
    ports:
      - "9100:9100"
```

Run it directly:

```bash
emerald-exchange-agent --host 0.0.0.0 --port 9100 \
  --mcp-url http://localhost:8100/mcp
```

## Behind a Caddy reverse proxy

Expose the HTTP server on a hostname with automatic TLS. Add to your `Caddyfile`:

```caddy
# Internal (self-signed) — homelab .arpa zone
emerald-exchange.arpa {
    tls internal
    reverse_proxy emerald-exchange-mcp:8100
}
```

```caddy
# Public — automatic Let's Encrypt
emerald-exchange.example.com {
    reverse_proxy emerald-exchange-mcp:8100
}
```

Reload Caddy:

```bash
docker compose -f services/caddy/compose.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## DNS with Technitium

Point the hostname at the host running Caddy. Via the Technitium API:

```bash
curl -s "http://technitium.arpa:5380/api/zones/records/add" \
  --data-urlencode "token=$TECHNITIUM_DNS_TOKEN" \
  --data-urlencode "domain=emerald-exchange.arpa" \
  --data-urlencode "zone=arpa" \
  --data-urlencode "type=A" \
  --data-urlencode "ipAddress=10.0.0.10" \
  --data-urlencode "ttl=3600"
```

…or add an **A record** `emerald-exchange.arpa → <caddy-host-ip>` in the Technitium
web console (`http://technitium.arpa:5380`). The ecosystem
[`technitium-dns-mcp`](https://knuckles-team.github.io/technitium-dns-mcp/) automates
this as a tool.

## Register with an MCP client

Add to your client's `mcp_config.json` (multiplexer nickname `ee`):

```json
{
  "mcpServers": {
    "emerald-exchange": {
      "command": "uv",
      "args": ["run", "emerald-exchange-mcp"],
      "env": {}
    }
  }
}
```

For a remote HTTP server, point the client at `http://emerald-exchange.arpa/mcp`
instead.
