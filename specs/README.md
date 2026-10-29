# Emerald Exchange specifications

These specs follow the ecosystem [spec standard](https://github.com/Knuckles-Team/pipelines/blob/main/reference/spec-standard.md): one owning spec per capability, extend an existing spec before creating one, audits and reviews land in the owning spec, one ID and title form, one file set. The `spec-standard` gate enforces it.

This tracked directory is the build contract for Emerald Exchange work. Each feature has `spec.md` (outcome and requirements), `plan.md` (architecture, interfaces and reuse), `test-spec.md` (acceptance and quality proof), `tasks.md` (implementation order), `requirements.md` (the definition of every requirement ID the feature owns), and `status.json` (delivery and acceptance state, with one entry per requirement ID in its `requirements` array, each carrying its own `delivery_state` and evidence). The files stand alone for public contributors; draft notes and private infrastructure are not prerequisites. A requirement counts as delivered only once its evidence includes a merged-head commit on the default branch.

Start a feature from [`_template/`](_template/) and follow the [repository constitution](../.specify/memory/constitution.md). `specs/` is the canonical feature tree; historical records under `.specify/specs/` remain legacy drafts until distilled. Run `python -m pytest tests/test_public_specs.py` to check the file and status contract.

| ID | Feature | State |
| --- | --- | --- |
| [EMERALD-OPS-001](exchange-operations/spec.md) | Read-only exchange operations as per-operation tools | SPECIFIED / NOT_AUDITED |
| [EMERALD-GUIDE-001](leveraged-trading-guide/spec.md) | Leveraged trading guide, gold example, skill and explainer contract | SPECIFIED / NOT_AUDITED |
| [EMERALD-MEDIA-001](finance-media-intake/spec.md) | Finance media evidence intake and strategy linkage | SPECIFIED / NOT_AUDITED |
| [CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT](connector-content/spec.md) | The connector serves its packaged content | VERIFIED / NOT_AUDITED |
| [CONN-EMERALD-EXCHANGE-XRPL](xrpl/spec.md) | XRPL agent wallet, payments and trading | SPECIFIED / NOT_AUDITED |
| [CONN-EMERALD-EXCHANGE-X402](x402/spec.md) | x402 pay-and-retry with Coinbase agent-wallet skill flavor | SPECIFIED / NOT_AUDITED |

`SPECIFIED` means a build contract exists. `BUILDING`, `BUILT`, `LANDED`, `CLOSED`, `DEFERRED`, `REJECTED`, and `UNKNOWN` describe delivery; `NOT_AUDITED`, `PENDING`, `ACCEPTED`, and `FAILED` describe acceptance independently. `LANDED` needs an owner-repository merged commit; `ACCEPTED` also needs the test and consumer receipts. Do not infer implementation from documentation.

Cross-repository owners: [epistemic-graph](https://github.com/Knuckles-Team/epistemic-graph/tree/main/specs) owns finance ontology, strategy evaluation, backtests and leverage math; [media-downloader](https://github.com/Knuckles-Team/media-downloader) owns caption/frame capture; [agent-webui](https://github.com/Knuckles-Team/agent-webui/tree/main/specs/finance-asset-manager) owns browser presentation; Emerald owns the derived finance skill, guide and governed effect boundary. Contributors may use [universal-skills](https://github.com/Knuckles-Team/universal-skills) spec-generator, spec-verifier and task-planner with [arbora-development](https://github.com/Knuckles-Team/arbora/tree/main/arbora/skills/arbora-development) to provision and navigate the ecosystem.

- [`EMERALD-OPS`](exchange-operations/spec.md) — Exchange read operations
- [`EMERALD-MEDIA`](finance-media-intake/spec.md) — Finance media intake
- [`EMERALD-GUIDE`](leveraged-trading-guide/spec.md) — Leveraged trading guide
- [`CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT`](connector-content/spec.md) — The connector serves its packaged content
- [`CONN-EMERALD-EXCHANGE-XRPL`](xrpl/spec.md) — XRPL agent wallet, payments and trading
- [`CONN-EMERALD-EXCHANGE-X402`](x402/spec.md) — x402 pay-and-retry with Coinbase agent-wallet skill flavor
