# syntax=docker/dockerfile:1
# Two right-sized images from ONE Dockerfile, selected by build --target. Both are
# slim multi-stage (build in a builder, ship only /usr/local — no dev-tools/source):
#
#   --target agent  (DEFAULT)  installs emerald-exchange[agent] = the FULL runtime
#                              (agent-utilities[agent-runtime]: pydantic-ai + dspy +
#                              skills; the full epistemic-graph engine is a mandatory
#                              base dependency of agent-utilities, present in both
#                              images). Because [agent] also includes [mcp], this image
#                              can run EITHER the agent OR the mcp server. Push as the
#                              default tags: latest / main / <version>.
#
#   --target mcp               installs emerald-exchange[mcp]   = MCP-server tooling ONLY
#                              (agent-utilities[mcp]: fastmcp/fastapi — NO pydantic-ai,
#                              dspy, llama-index, tree-sitter agent-orchestration stack;
#                              the epistemic-graph engine is still present, it's a base
#                              dependency). The slim variant. Push as the
#                              :mcp / :mcp-<version> tag.
#
#   docker build --target agent -t emerald-exchange:latest .
#   docker build --target mcp   -t emerald-exchange:mcp    .
FROM python:3.11-slim@sha256:e031123e3d85762b141ad1cbc56452ba69c6e722ebf2f042cc0dc86c47c0d8b3 AS builder-base
COPY --from=ghcr.io/astral-sh/uv:0.11.7@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_PYTHON=1 \
    UV_HTTP_TIMEOUT=3600
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Slim MCP-only dependency closure.
FROM builder-base AS builder-mcp
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --upgrade --break-system-packages --prerelease=allow emerald-exchange[mcp]>=1.0.1

# Full agent runtime dependency closure.
FROM builder-base AS builder-agent
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --upgrade --break-system-packages --prerelease=allow emerald-exchange[agent]>=1.0.1

FROM python:3.11-slim@sha256:e031123e3d85762b141ad1cbc56452ba69c6e722ebf2f042cc0dc86c47c0d8b3 AS runtime-base
ARG HOST=127.0.0.1
ARG PORT=8000
ARG TRANSPORT="stdio"
ARG AUTH_TYPE="none"
ENV HOST=${HOST} \
    PORT=${PORT} \
    TRANSPORT=${TRANSPORT} \
    AUTH_TYPE=${AUTH_TYPE} \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}" \
    UV_HTTP_TIMEOUT=3600 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Fixed identity for least-privilege runtime and stable volume ownership.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
        --home-dir /tmp --shell /usr/sbin/nologin app
ENV HOME=/tmp \
    XDG_CONFIG_HOME=/tmp/.config \
    XDG_CACHE_HOME=/tmp/.cache

# Slim image: MCP server only.
FROM runtime-base AS mcp
USER 10001:10001
COPY --from=builder-mcp /usr/local /usr/local
CMD ["emerald-exchange-mcp"]

# Full image (DEFAULT target): agent runtime; can also run the mcp server.
FROM runtime-base AS agent
USER 10001:10001
COPY --from=builder-agent /usr/local /usr/local
CMD ["emerald-exchange-agent"]
