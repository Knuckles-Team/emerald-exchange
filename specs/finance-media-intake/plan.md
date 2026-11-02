# EMERALD-MEDIA — Implementation plan

Governing spec: [spec.md](spec.md). Rows: [requirements.md](requirements.md).

## Summary

This plan delivers finance media intake for the connector, reusing the SDK for shared capabilities.

## Technical Context

- **Language/Version**: Python 3.14 (floor 3.12)
- **Primary Dependencies**: scion-sdk, fastmcp
- **Storage**: N/A; the connector stores nothing
- **Testing**: pytest; the proof level each row names
- **Target Platform**: Linux containers
- **Project Type**: connector (MCP server)
- **Performance Goals**: N/A
- **Constraints**: one tool per API operation; shared capabilities come from the SDK
- **Scale/Scope**: 1 rows

## Constitution Check

- One owner per concept: pass. The connector owns one external system's calls, mappings and tools only.
- Connectors depend on the SDK and are called through arbora: pass.
- No ratchets: pass. The rows add no suppression.

## Project Structure

```text
emerald_exchange/skills/__init__.py  existing
specs/finance-media-intake/spec.md  existing
```

## Phase 0: Research

No unknowns. Each row names the code it touches.

## Phase 1: Design

### Existing wiring

Reuse media-downloader's `media-watch` `watch_media`, `list_watch_skills` and `build_watch_skill` sequence. The capture bundle already includes `manifest.json`, transcript, caption track, timestamped frames and availability states. Its builder owns source provenance and generated `WORKFLOW.md`. Reuse Emerald's `emerald_exchange/skills/` conventions for the reviewed finance skill. EG owns strategy IDs and backtest records; Emerald stores links, not a second evaluator. Use the existing KG ingestion path only for indexing after Git content is reviewed; Git is the public source of truth.

### Evidence and skill data

For each source, retain a reviewable record with canonical URL, topic, capture UTC time, article publication/effective date if known, content digest, caption language/status, transcript origin (`CAPTION` or `ASR`), frame status/count, and provenance-safe evidence spans. For each extracted item: source ID, timestamp or article section, kind (`STEP`, `WARNING`, `CLAIM`, `OBSERVATION`, `INFERENCE`), bounded paraphrase, confidence, reviewer state, and linked `StrategySpec` ID/version or `UNMAPPED`. Do not commit entire copyrighted transcripts, video, images, tokens or private capture paths. A source disappearing leaves an unavailable receipt and pending task, not fictional content.

Two derived skill topics suffice initially: DCA and leveraged trading. Check `list_watch_skills` before creating; append if the new source adds consistent evidence, replace with an explicit supersession note when a claim/conclusion changes. `What would change this skill` names out-of-sample, fee/slippage/tax and adverse-regime evidence that could overturn each finance claim. `build_watch_skill` writes frontmatter/provenance/WORKFLOW; reviewer verifies the resulting tracked files before merge.

### Promotion boundary

`media-watch` bundle → extraction/reviewer → Emerald skill with claim statuses → EG `StrategySpec` mapping → EG backtest/evidence → AU recommendation projection. A source claim is `UNTESTED` by default. Only version-matched accepted backtest evidence can change its eligibility for informational recommendation; a stale strategy version, missing costs, thin history, drift or failed validation forces abstention. No edge from media intake goes to Emerald order tools or the execution bridge. This is a content and evidence flow, not a trading executor.

### Quality and compatibility

Keep one source table and one rule-link schema across both skills (KISS); avoid a new downloader, duplicate strategy engine, or second provenance database. If changed source code adds parsing, run repo lint/tests and configured CCCC, jscpd and Dupehound gates; record their actual commands and thresholds, or declare missing configuration rather than inventing a result. Preserve skill/frontmatter compatibility with existing catalog loaders.

## Phase 2: Task approach

`tasks.md` holds one task line per row, producer first.

## Complexity Tracking

None. The constitution check passed.

## Build contract

The repository pre-commit hooks apply: `ruff-format`, `connector-standard`, `secrets`, `tests-fast`. Each row names its proving test. No suppression and no duplicate implementation.

## Production caller chain

1. `EMERALD-MEDIA-R001`: (planned intake) media-watch agent run -> emerald_exchange/skills/<skill>/capture_log.json served as skill:// by ConnectorContent.for_package (mcp_server.py:14); guard: console script emerald-exchange-mcp (pyproject.toml project.scripts) -> emerald_exchange/mcp_server.py::mcp_server -> get_mcp_instance -> tool emerald_strategy (emerald_exchange/mcp/mcp_strategy.py:11) -> new emerald_exchange/strategy_links.py::require_mapped_strategy.

## Cross-repo seams

none
