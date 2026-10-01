# EMERALD-GUIDE-001 — Design and architecture

## Existing wiring and reuse

Emerald already has `emerald_exchange/skills/`, public documentation, `RiskGuard`, `ExecutionBridge`, `create_backend()` and a paper default. Use a single reviewed Markdown/content revision as the source for the skill and WebUI projection; avoid independent copies with drifting figures. The skill follows the existing `SKILL.md`/`WORKFLOW.md` catalog pattern. Numeric leverage analysis stays in EG finance rather than new Python finance math. The WebUI consumes a read-only guide projection from Graph OS; it does not read Emerald files from a browser or embed broker credentials.

## Content contract

Each guide revision carries `guide_id=EMERALD-GUIDE-R001`, semantic revision, locale, reviewed timestamp, reviewer, source cards, vehicle sections, assumptions, example inputs, and verified output references. Source cards carry public URL, publisher, document revision/effective date, capture time, claim text or bounded paraphrase, and validation state (`SOURCE_ASSERTION`, `PRIMARY_CONFIRMED`, `TESTED`, `REJECTED`). A `StrategySpec` reference includes stable ID and version; an educational-only rule is explicitly tagged. Stable anchors and structured headings allow accessible WebUI deep links. Publish only source quotations within license limits.

The worked gold example has an **illustrative fixed input fixture**, never a current broker quote: instrument/contract, quantity, multiplier, price, collateral, maintenance threshold, fees and adverse/gap scenarios. Amounts use decimal strings and units. EG returns derived levels and provenance; the guide compares them with independently hand-calculated expected values. Futures expiry/roll, ETF daily reset and financing are separate branches, never collapsed into one generic multiplier.

## Data flow and failure behavior

EMERALD-MEDIA-R001 intake → editor/source verification → canonical guide revision → Emerald skill + public guide → Graph OS read-only projection → WebUI explainer. EG-FINANCE-PRIMITIVES-R010 supplies calculations when a simulation is requested; if unavailable, stale, terms missing, unsupported, or jurisdiction ineligible, show explanatory content and a clear simulation-unavailable reason. Do not substitute a guessed price, margin rate or instrument. No edge from the content/projection flow enters `mcp_orders` or `ExecutionBridge.route()`.

## Quality and compatibility

Keep the existing skill registry and docs build paths; add no second strategy evaluator, execution adapter, or finance policy store. If a typed projection is necessary, version its schema and test an older reader against additive fields. Use concise content, a single source-card structure and shared references (KISS). CCCC, jscpd and Dupehound apply to changed executable code; record the repository-configured command and threshold, or note a missing configuration before claiming a pass. Review generated skill/content parity and keep no copied transcript as a public spec.
