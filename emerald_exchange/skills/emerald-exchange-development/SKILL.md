---
name: emerald-exchange-development
skill_type: skill
domain: development
description: >-
  Develop, test, gate, and release the emerald-exchange connector. Use this skill when
  changing the connector's API mappings, MCP tools, packaging, documentation,
  or repository gates.
license: MIT
tags: [emerald-exchange, development, connector, test, gates]
tier: repository
metadata:
  author: Genius
  version: '0.2.0'
---

# emerald-exchange development

This repository owns the Emerald Exchange finance connector: the exchange backends (paper, Alpaca, ccxt, Binance, Kalshi, CLOB), risk guards, market-data, fundamentals and wallet-intelligence tool groups, and their MCP tools. Shared connector contracts and transports belong to `scion-sdk`;
admission, serving, and durable graph state belong to their owning
repositories. Read `AGENTS.md` before changing code and keep provider
credentials and endpoints out of source, logs, and skill content.

Hard rules from `AGENTS.md`: orders always pass `RiskGuard.pre_trade_check()`,
the default backend is `PaperBackend` (never default to live), backends come
from the `create_backend()` factory, and numeric/quant compute is delegated to
the `epistemic-graph` engine rather than re-implemented with numpy/scipy.

## Rapid delivery: the 5-minute contract

Specs are already designed. Deliver small, reviewable slices and cite the
owning spec row in the commit trailer.

- Find the owning row first with `git grep -n "<term>" -- specs` and extend
  that spec before adding new requirement text.
- Reuse existing SDK clients, transport policies, and tool factories. Do not
  create a second implementation of a connector capability.
- Keep changes scoped to this connector. A change owned by the SDK, Arbora,
  or the knowledge graph belongs in that repository instead.
- Every delivered requirement needs a bound test. Generated `status.json`
  files are produced by `pipelines-hook spec-status`; never hand-edit them.
- One logical change per commit, with `Spec: <ID>` and the assisting agent
  trailer adjacent in the final paragraph.

## Setup and gates

Use the pinned environment from `uv sync --locked --all-extras`. Run the
repository gate from the checkout root:

```bash
uvx pre-commit run --all-files
```

For focused feedback, run the relevant tests with the repository's pinned
environment, for example:

```bash
uv run --all-extras pytest tests/test_order_guard.py -q
uv run --all-extras pytest tests/test_kg_ingest.py tests/test_fleet_name.py -q
uv run --all-extras pytest tests/test_default_content_surfaces.py -q
```

The canonical `.pre-commit-config.yaml` delegates connector-standard,
secrets, spec, tests-fast, and dependency-readiness checks to
`Knuckles-Team/pipelines` at `rev: main`. Do not replace those shared hooks
with local copies or bypass a failing check.

## Connector-specific checks

- Mock every exchange and data provider (Alpaca, ccxt, Binance, Kalshi, CLOB,
  SEC EDGAR, FMP); never place live orders or use live credentials in a gate.
- Heavy providers (`edgartools`, `polars`, `py-clob-client`) stay optional and
  lazily imported; the package must import without them.
- Every MCP tool docstring names its `CONCEPT:EE-*` id.
- The `test` extra pins `epistemic-graph[server]`; keep that bound compatible
  with the engine floor required by `scion-sdk`, then refresh `uv.lock`.
- Keep the MCP surface aligned with `scion-sdk`; read the version from package
  metadata rather than spelling it in a module.
- Keep `emerald_exchange/skills/` package data intact when adding skills.
- Documentation lives under `docs/` and is published by the shared Pages
  workflow; source status records live under `specs/`.

## Delivery discipline

Work in a real Git worktree based on `origin/main`. Inspect the complete diff,
stage only reviewed paths, and verify `git status --short` after every gate.
Do not use `git stash`, `git add -A`, or `git add .`; do not claim Pages
publication until a successful exact-source workflow run and the public page
are both observed.
