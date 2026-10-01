# EMERALD-GUIDE-001 — Leveraged trading guide

**Owner:** Emerald Exchange. **Delivery:** SPECIFIED. **Acceptance:** NOT_AUDITED.

See [`requirements.md`](requirements.md) for the definition of every requirement ID this spec owns and [`status.json`](status.json) for their current delivery and acceptance state.

## Outcome and scope

A reader can understand how leverage changes exposure, collateral requirements, losses, and forced liquidation before exploring a **paper** gold position. Publish one versioned, evidence-backed written guide in Emerald's public documentation and skill catalog, with a typed content contract for the WebUI explainer. This is educational content and simulation, not a signal or an order. Current implementation is unverified.

## User stories and acceptance

1. A beginner compares an unleveraged gold exposure with a fixed-notional leveraged position and can identify notional, equity, borrowed or margined exposure, initial and maintenance margin, fees, price movement, margin call and liquidation. The worked example states assumptions, currency, timestamp, source, and arithmetic; a reader can reproduce every figure.
2. A reader can compare four distinct vehicles without conflating them: a margin account holding a gold security, exchange-traded standard/micro gold futures, daily-reset leveraged ETFs, and retail FX leverage. For each, explain eligibility/jurisdiction, contract or fund mechanics, financing/margin, expiry/roll or daily reset, liquidity, gap loss, and path dependence where applicable. Do not present a CFD as an available US retail route without verified current eligibility.
3. A reader sees a margin-call/liquidation sensitivity table and risk-of-ruin illustration from the engine's leverage capability (EG-FINANCE-PRIMITIVES-R010), including stale/unknown terms as an explicit refusal to calculate. Narrative examples may be hand checked, but live product calculations must call the engine.
4. An agent can invoke a versioned `emerald-exchange-leveraged-trading` skill whose steps distinguish source-derived claims from validated mechanics, link each mechanical rule to a versioned `StrategySpec` ID or mark it educational-only, and state what evidence would revise it.
5. The WebUI receives the same guide revision and source/effective-date metadata as the skill and documentation. It labels the explainer educational and clearly distinguishes paper simulation, proposed action and live execution. A link or explainer action cannot submit an order.

## Functional requirements

| ID | Requirement | Proof |
| --- | --- | --- |
| GUIDE-1 | One canonical guide revision feeds public guide, Emerald skill and WebUI explainer content; each displays revision and reviewed date | Content parity check |
| GUIDE-2 | Gold example has reproducible units and formulas for exposure, P/L, collateral, maintenance threshold and adverse gaps; no invented current rates | Fixture and source review |
| GUIDE-3 | Vehicle comparison includes policy/eligibility caveats, rollover and daily-reset decay where relevant | Editorial checklist |
| GUIDE-4 | Numerical simulation delegates to EG-FINANCE-PRIMITIVES-R010 and refuses absent/stale/ineligible terms | Contract and negative tests |
| GUIDE-5 | Source cards identify publisher, public URL, publication or effective date, capture/review time, exact claim and confidence/verification state | Provenance audit |
| GUIDE-6 | No recommendation or live effect follows solely from video assertions or guide interaction | Integration test |

## Boundaries and dependencies

EMERALD-MEDIA-R001 supplies media evidence, but the guide also uses current primary exchange contract specifications and regulator rules reviewed at publication. EG-FINANCE-PRIMITIVES-R010 in [epistemic-graph](https://github.com/Knuckles-Team/epistemic-graph/tree/main/specs) owns leverage terms and numeric simulation; EG-FINANCE-PRIMITIVES-R007/703 own `StrategySpec` and evidence from backtests. [agent-webui Finance](https://github.com/Knuckles-Team/agent-webui/tree/main/specs/finance-asset-manager) renders the explainer. Emerald's existing `RiskGuard.pre_trade_check()`, `ExecutionBridge.route()` and paper default remain the sole effect path; this guide adds no order path. Live leveraged execution requires a separate explicit per-instrument policy, valid approval lease, designated approvers and existing risk guards. No spec text grants such approval.

## Exclusions and completion

This spec does not implement derivatives pricing, legal eligibility decisions, a live trading strategy, or automated leverage. Completion requires published parity across guide/skill/explainer, verified current primary-source citations, EG-FINANCE-PRIMITIVES-R010 consumer contract tests, the negative order test, and a merged owner revision recorded in `status.json` before `LANDED`; acceptance needs independent evidence. Investment and regulatory facts are reviewed against current official sources at implementation, not frozen from a video.
