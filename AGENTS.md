# AGENTS.md — emerald-exchange

> Claude Code loads this file via `CLAUDE.md` (`@AGENTS.md` import) — the two stay
> in sync. Edit **this** file, not `CLAUDE.md`.

> AI coding agent context for `emerald-exchange`

## ⚙️ Quant compute lives in epistemic-graph (READ FIRST)

Exchange backends (alpaca/ccxt/binance/kalshi/clob) are **I/O glue and stay in
Python**. But any **numeric/quant** work — portfolio optimization, risk metrics
(VaR/CVaR/Sortino/drawdown/stress), regime detection (HMM), alpha signals
(z-score/EWMA/momentum/IC), execution math (TWAP/VWAP/market-impact/pairs) — must
be delegated to the Rust **`epistemic-graph`** engine, not re-implemented with
`numpy`/`scipy`.

- Call it via `epistemic_graph.client` (`.finance` / `.datascience` namespaces),
  directly or through `agent-utilities/domains/finance/*` (which already routes
  portfolio optimization to the engine).
- **When enhancing or adding quant features, extend the engine** and call it from
  here — see `epistemic-graph/docs/RUST_COMPUTE_GUIDE.md` for the capability list
  and how to expose a new one. Keep only trivial per-order arithmetic (e.g. Kelly
  sizing, position caps) inline.
- Do not add `scipy`/heavy-`numpy` compute paths to this package.

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
│   ├── data/                # Data/fundamentals providers (optional deps, lazy)
│   │   ├── edgar.py         # SEC EDGAR (edgartools) — CONCEPT:EX-AHE.harness.ee-26
│   │   └── wallet_intel.py  # Polymarket wallet analytics — CONCEPT:EX-AHE.harness.ee-27
│   └── mcp/                 # Tool domains
│       ├── mcp_market_data.py
│       ├── mcp_orders.py
│       ├── mcp_portfolio.py
│       ├── mcp_risk.py
│       ├── mcp_signals.py
│       ├── mcp_strategy.py
│       ├── mcp_fundamentals.py    # emerald_fundamentals — CONCEPT:EX-AHE.harness.ee-26
│       └── mcp_wallet_intel.py    # emerald_wallet_intel — CONCEPT:EX-AHE.harness.ee-27
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

## Fundamentals & Wallet-Intelligence Tool Groups

Two data-provider tool groups were folded in from the former standalone
`edgar-mcp` and `poly-wallet-mcp` packages so emerald-exchange is the single
multi-asset finance hub (execution + market data + risk + fundamentals +
wallet-intel). Both keep their heavy third-party deps (`edgartools` / `polars` /
`py-clob-client`) **optional and lazily imported** — emerald imports cleanly
without them, surfacing a clear `{"error": ...}` payload when a call needs an
absent dependency, identity, dataset, or engine.

### `emerald_fundamentals` — SEC EDGAR (CONCEPT:EX-AHE.harness.ee-26)

Action-routed (`action`, `params_json`). Env gate `FUNDAMENTALSTOOL` (set falsey
to disable); SEC identity from `EDGAR_IDENTITY` (`"Name email@example.com"`).
Optional dep: `edgartools` (`pip install 'emerald-exchange[fundamentals]'`).

- `filings` — latest N filings of a form (10-K/10-Q/8-K).
- `financials` — standardized income / balance / cashflow statement.
- `risk_factors` — Item 1A, this year + prior year (for diffing).
- `mdna` — Item 7 MD&A, this year + prior year.
- `full_text_search` — EDGAR phrase search (e.g. "material weakness").
- `standardize` — two latest fiscal years → exact 17-key forensic schema.
- `forensic_screen` — chains `standardize_financials` → engine
  `forensic_report` (Beneish M / Altman Z / Piotroski F / Sloan accruals) so a
  single ticker goes filings → standardize → verdict in ONE call. Reuses
  `forensic.py` / `_engine.py`; degrades gracefully when the engine socket is
  absent.

### `emerald_wallet_intel` — Polymarket wallet analytics (CONCEPT:EX-AHE.harness.ee-27)

Action-routed (`action`, `params_json`). Env gate `WALLETINTELTOOL` (set falsey
to disable); dataset path from `POLY_TRADES_PATH` (a `poly_data` processed-trades
CSV/Parquet). Optional dep: `polars` (Parquet / fast loader —
`pip install 'emerald-exchange[wallet_intel]'`); pure-Python over a stdlib-CSV
fallback otherwise.

- `rank_wallets` — smart-money copy-trade targets (filter by trades + win rate).
- `wallet_profile` — per-wallet stats + open positions.
- `smart_money_convergence` — how many target wallets hold the same side.
- `exit_behavior` — % exit before resolution + avg % max profit captured.

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

## Working Discipline — think, simplify, stay surgical, verify

These four habits cut the most common LLM coding mistakes. For trivial tasks, use
judgment; the bias here is correctness over speed.

- **Think before coding.** State your assumptions explicitly. If a request has more than
  one reasonable reading, surface the options instead of silently picking one. If a
  simpler approach exists, say so and push back when warranted. When something is
  genuinely unclear, stop and name what's confusing — ask, don't guess.
- **Simplicity first.** Write the minimum code that solves the stated problem — no
  speculative features, no abstraction for single-use code, no configurability that
  wasn't requested, no error handling for impossible states. If you wrote 200 lines and
  it could be 50, rewrite it. (Name code from its purpose, never `wave0`/`phase2`/`v2`.)
- **Stay surgical.** Every changed line should trace directly to the task. Don't refactor,
  reformat, or "improve" working code adjacent to your change; match the existing style
  even where you'd do it differently. Remove only the imports/symbols your own change
  orphaned; if you spot unrelated dead code, mention it rather than deleting it inline.
  *Exception — the Quality Bar below:* lint/format/type errors the pre-commit gate flags
  get fixed regardless of who introduced them. In short: **surgical on behavior, clean on
  lint.**
- **Verify against a goal.** Turn the task into a checkable outcome before you start:
  "fix the bug" → "write a failing test that reproduces it, then make it pass"; "add
  validation" → "tests for the invalid inputs pass". For multi-step work, state the short
  plan and the check for each step, then loop until the checks pass.

## Quality Bar — Leave the Codebase Clean (REQUIRED)

After completing any code change, run the project's pre-commit suite and drive it
**fully green** before committing:

```bash
pre-commit run --all-files
```

Resolve **every** issue it reports — failures, lint errors, type errors, and
warnings — **including problems that pre-date your change and were not caused by
your edits**. The standing goal is a clean, working codebase with **no errors and
no warnings**. Do not silence checks (`# noqa`, `# type: ignore`, `SKIP=`,
`--no-verify`) to force green unless the exception is already documented in this
file as a known, unavoidable limitation. Only commit once `pre-commit run
--all-files` passes cleanly; if a check legitimately cannot pass, stop and explain
why rather than bypassing it.

## Working with Git Worktrees (multi-session)

Multiple agents/sessions work the `agent-packages/*` repos concurrently. **Do not
edit the canonical checkout** (`/home/apps/workspace/agent-packages/<repo>`) — a
background `repository-manager` sync can reset its working tree and discard
uncommitted edits. Take your own git worktree on your own branch instead:

```bash
# preferred — repository-manager MCP:
rm_worktree add <repo> <your-branch>      # -> /home/apps/worktrees/<repo>/<your-branch>

# raw-git fallback:
git -C agent-packages/<repo> checkout main
git -C agent-packages/<repo> worktree add /home/apps/worktrees/<repo>/<branch> -b <branch>
```

Work in the worktree and **commit often** (commits survive a working-tree reset).
Each session must use a **distinct branch** — git allows a branch in only one
worktree, which is what keeps concurrent sessions from colliding. Worktrees live
under `/home/apps/worktrees/` (outside the workspace scan, so the sync leaves them
alone).

**Finishing work in a worktree** — run this sequence before calling it done:
1. **Pre-commit green** — `pre-commit run --all-files`; resolve every issue per the
   Quality Bar above (including pre-existing), no `--no-verify`.
2. **Commit** in the worktree.
3. **Merge to main locally** — `rm_worktree merge <repo> <branch> --into main`
   (or `git merge --no-ff`). Push only when the user asks.
4. **Clean up** — remove the worktree and delete the merged branch:
   `rm_worktree remove <repo> <branch> --delete-branch`; `rm_worktree prune` clears
   stale entries. (Raw-git: `git worktree remove <path> && git branch -d <branch>`.)

<!-- BEGIN concept-coordination (generated) -->
## Concept-ID Coordination (multi-session)

Working in parallel with other sessions/worktrees? **Reserve a concept id before you write its `CONCEPT:` marker** so two sessions never collide:

```bash
agent-utilities --json concept reserve --ns EG-KG.compute.backend   # or a package prefix, e.g. KEY
```

Full protocol (ledger, merge=union, reconcile, MCP/REST): <https://knuckles-team.github.io/agent-utilities/concept_coordination/>
<!-- END concept-coordination (generated) -->
