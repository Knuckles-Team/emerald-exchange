# EMERALD-MEDIA-001 — Finance media intake

**Owner:** Emerald Exchange for the resulting finance skills and claim/strategy linkage. **Delivery:** SPECIFIED. **Acceptance:** NOT_AUDITED.

See [`requirements.md`](requirements.md) for the definition of every requirement ID this spec owns and [`status.json`](status.json) for their current delivery and acceptance state.

## Outcome and sources

An external contributor can capture designated DCA and gold/leverage material, separate what a source demonstrates from what it asserts, and produce reviewable Emerald skills with provenance. `media-downloader` owns capture; Emerald owns interpretation and skill publication. No video is assumed watched or verified by this specification.

| Public source | Intended topic | Intake method |
| --- | --- | --- |
| https://www.investopedia.com/terms/d/dollarcostaveraging.asp | Dollar-cost averaging | Read article directly with URL and capture time |
| https://youtube.com/shorts/aa4j13o1gWk | DCA | `media-watch`, English captions (`en`) |
| https://youtube.com/watch?v=wENEfGzuRVA | DCA | `media-watch`, English captions (`en`) |
| https://youtube.com/watch?v=mQS1tCQUiAM | DCA | `media-watch`, English captions (`en`) |
| https://www.youtube.com/watch?v=W15yaLU--KA | Gold and leverage | `media-watch`, English captions (`en`) |

## User stories and acceptance

1. A contributor runs `media-watch` for each video and records the public URL, capture time, media/caption/frames state, caption language, transcript origin, and time-coded evidence. They request `en` explicitly; a wildcard must not trigger extra language downloads or rate limits.
2. A reviewer can distinguish source steps, screen-observed details, warnings, source claims, editor inference, and independently verified mechanics. Missing captions or frames remain visible; no fabricated observation fills a gap. For missing captions, use the audio-transcriber fallback only when the lawful local media file is available and label ASR output.
3. A published Emerald skill contains a versioned source table, reproducible steps, warnings, claim statuses, and `What would change this skill`. Each mechanical trading rule links to an EG `StrategySpec` stable ID and version, or is marked `UNMAPPED` and cannot drive a recommendation. The DCA skill references schedule, amount/share policy and value-averaging variants only when the tested strategy contract supports them.
4. A claim can affect a recommendation only after EG-FINANCE-PRIMITIVES-R008 produces a `BacktestRun` with out-of-sample/purged validation, deflated Sharpe, probability-of-backtest-overfitting, costs and versioned evidence; the recommendation remains informational and can abstain. Media popularity or narrator confidence is never an evidence substitute.

## Requirements

| ID | Requirement | Evidence |
| --- | --- | --- |
| MEDIA-1 | Exact source set, URL, capture time and availability manifest are recorded | Public source table and sanitized manifest |
| MEDIA-2 | English captions are requested as `en`; failures and ASR provenance are explicit | Capture log/fixture |
| MEDIA-3 | Time-coded steps, claims, warnings and observed frames are distinct; inferred content is labeled | Reviewer sample |
| MEDIA-4 | Reusable skills use the existing Emerald catalog and media-watch provenance contract, with no duplicate source ingestion store | Skill parser and catalog check |
| MEDIA-5 | Mechanical rules map to versioned `StrategySpec` or `UNMAPPED`; claimed outcomes cannot self-promote to recommendation | Contract and negative tests |
| MEDIA-6 | Backtest evidence and abstention are required before recommendation consumption | EG/AU consumer receipt |

## Boundaries and completion

[media-downloader](https://github.com/Knuckles-Team/media-downloader/tree/main/media_downloader/skills/media-watch) owns `watch_media`, frame extraction, caption capture, manifests and `build_watch_skill`. [epistemic-graph](https://github.com/Knuckles-Team/epistemic-graph/tree/main/specs) owns `StrategySpec`, deterministic evaluation and `BacktestRun` (EG-FINANCE-PRIMITIVES-R007/703). Emerald owns curated DCA and leverage skills and their links; [agent-webui Finance](https://github.com/Knuckles-Team/agent-webui/tree/main/specs/finance-asset-manager) consumes only reviewed informational content. EMERALD-GUIDE-R001 consumes the leverage intake. No media-derived content invokes `mcp_orders` or authorizes a live trade. Completion requires all five source receipts or explicit unavailable results, reviewed skills, rule mappings, negative gating tests and a merged Emerald revision; acceptance requires exact consumer evidence.
