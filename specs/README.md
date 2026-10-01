# Emerald Exchange specifications

This tracked directory is the build contract for Emerald Exchange work. Each feature has `spec.md` (outcome and requirements), `plan.md` (architecture, interfaces and reuse), `test-spec.md` (acceptance and quality proof), `tasks.md` (implementation order), `requirements.md` (the definition of every requirement ID the feature owns), and `status.json` (delivery and acceptance state, with one entry per requirement ID in its `requirements` array, each carrying its own `delivery_state` and evidence). The files stand alone for public contributors; draft notes and private infrastructure are not prerequisites. A requirement counts as delivered only once its evidence includes a merged-head commit on the default branch.

Start a feature from [`_template/`](_template/) and follow the [repository constitution](../.specify/memory/constitution.md). `specs/` is the canonical feature tree; historical records under `.specify/specs/` remain legacy drafts until distilled. Run `python -m pytest tests/test_public_specs.py` to check the file and status contract.

| ID | Feature | State |
| --- | --- | --- |
| [EMERALD-GUIDE-001](leveraged-trading-guide/spec.md) | Leveraged trading guide, gold example, skill and explainer contract | SPECIFIED / NOT_AUDITED |
| [EMERALD-MEDIA-001](finance-media-intake/spec.md) | Finance media evidence intake and strategy linkage | SPECIFIED / NOT_AUDITED |

`SPECIFIED` means a build contract exists. `BUILDING`, `BUILT`, `LANDED`, `CLOSED`, `DEFERRED`, `REJECTED`, and `UNKNOWN` describe delivery; `NOT_AUDITED`, `PENDING`, `ACCEPTED`, and `FAILED` describe acceptance independently. `LANDED` needs an owner-repository merged commit; `ACCEPTED` also needs the test and consumer receipts. Do not infer implementation from documentation.

Cross-repository owners: [epistemic-graph](https://github.com/Knuckles-Team/epistemic-graph/tree/main/specs) owns finance ontology, strategy evaluation, backtests and leverage math; [media-downloader](https://github.com/Knuckles-Team/media-downloader) owns caption/frame capture; [agent-webui](https://github.com/Knuckles-Team/agent-webui/tree/main/specs/finance-asset-manager) owns browser presentation; Emerald owns the derived finance skill, guide and governed effect boundary. Contributors may use [universal-skills](https://github.com/Knuckles-Team/universal-skills) spec-generator, spec-verifier and task-planner with [graph-os-development](https://github.com/Knuckles-Team/graph-os/tree/main/graph_os/skills/graph-os-development) to provision and navigate the ecosystem.
