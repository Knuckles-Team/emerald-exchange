# Deployment

<!-- BEGIN GENERATED: deployment-options -->
## Deployment Options

`emerald-exchange` supports local stdio, a loopback-only development listener, a
least-privilege stdio container, and a remote authenticated HTTPS boundary.
Provider endpoint, credential, selector, identity, and trust material are supplied
at runtime through `AgentConfig`; none is stored in this repository.

### Installed stdio process

```json
{
  "mcpServers": {
    "emerald-exchange": {
      "command": "emerald-exchange-mcp",
      "args": [],
      "env": {"MCP_TOOL_MODE": "intent"}
    }
  }
}
```

### Loopback development listener

```bash
emerald-exchange-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

Do not expose this listener beyond loopback. Network deployments require direct TLS
or an explicitly trusted TLS-terminating ingress, configured authentication, exact
`MCP_ALLOWED_HOSTS`, and an exact trusted-proxy CIDR policy.

### Least-privilege local container

```bash
docker run -i --rm \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --pids-limit=256 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
  -e TRANSPORT=stdio \
  registry.example.invalid/emerald-exchange@sha256:<digest> emerald-exchange-mcp
```

The operator projects the selected AgentConfig profile into the process at runtime;
the image remains immutable and contains no environment connection profile.

### Remote authenticated HTTPS endpoint

```json
{
  "mcpServers": {
    "emerald-exchange": {"url": "https://service.example.invalid/mcp"}
  }
}
```

Store the real remote URL, outbound identity reference, and TLS-profile reference in
`AgentConfig`, not in MCP client JSON or documentation.
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
    image: example/emerald-exchange@sha256:<digest>
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
    image: example/emerald-exchange@sha256:<digest>
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
# Internal (self-signed) — homelab .example.invalid zone
emerald-exchange.example.invalid {
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
curl -s "http://technitium.example.invalid:5380/api/zones/records/add" \
  --data-urlencode "token=$TECHNITIUM_DNS_TOKEN" \
  --data-urlencode "domain=emerald-exchange.example.invalid" \
  --data-urlencode "zone=arpa" \
  --data-urlencode "type=A" \
  --data-urlencode "ipAddress=192.0.2.10" \
  --data-urlencode "ttl=3600"
```

…or add an **A record** `emerald-exchange.example.invalid → <caddy-host-ip>` in the Technitium
web console (`http://technitium.example.invalid:5380`). The ecosystem
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

For a remote HTTP server, point the client at `http://emerald-exchange.example.invalid/mcp`
instead.
