# AGENTS.md — emerald-exchange

> Claude Code loads this file via `CLAUDE.md` (`@AGENTS.md` import) — the two stay
> in sync. Edit **this** file, not `CLAUDE.md`.

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

## ⛔ No Scratch or Temporary Files in Repository

**NEVER write any of the following to this repository:**
- Temporary test scripts (`test_*.py`, `debug_*.py` outside of `tests/`)
- Scratch scripts or experimental one-off files
- Log files (`.log`, `.txt` command output)
- Random text files with command output or debug dumps
- Any file that is NOT production source code, tests in `tests/`, or documentation

**Why:** These files expose private filesystem paths, credentials, and internal infrastructure details when pushed to GitHub publicly.

**Where to put scratch work instead:**
- Use `~/workspace/scratch/` for temporary scripts and experiments
- Use `~/workspace/reports/` for command output and reports
- Keep test scripts in the `tests/` directory following proper pytest conventions

## ⛔ Keep the Repository Root Pristine — No Scratch / Temp / Debug Files

**The repository ROOT must contain only canonical project files** (packaging,
config, docs, lockfiles). The only hidden directories allowed at root are
`.git/`, `.github/`, and `.specify/` (plus a local, git-ignored `.venv/`).

**NEVER write any of the following — anywhere in the repo, and ESPECIALLY at the root:**
- One-off / debug / migration scripts: `fix_*.py`, `migrate_*.py`, `refactor_*.py`,
  `replace_*.py`, `update_*.py`, `debug_*.py`, or `test_*.py` **at the root**
  (real tests live in `tests/` only).
- Databases / data dumps: `*.db`, `*.db-wal`, `*.sqlite*`, `*.corrupted`.
- Logs / command output: `*.log`, scratch `*.txt`, `*.orig`, `*.rej`, `*.bak`.
- Build artifacts: `*.tsbuildinfo`, compiled binaries, coverage files.
- AI agent scratch directories: `.agent/`, `.agents/`, `.agent_data/`, `.tmp/`,
  `.hypothesis/`, or any per-tool cache committed to git.
- Any file that is NOT production source, a test in `tests/`, documentation, or
  a recognized config/lockfile.

**Why:** scratch at the root leaks private paths/credentials, bloats the tree,
and erodes a pristine codebase.

**Where scratch goes instead:** `~/workspace/scratch/` (experiments),
`~/workspace/reports/` (command output); tests go in `tests/` (pytest).
Before finishing a task, run `git status` and confirm no stray root files were added.
