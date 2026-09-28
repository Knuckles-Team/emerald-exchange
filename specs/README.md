# Emerald Exchange specifications

This tracked directory is the build contract for Emerald Exchange work. Each feature has `spec.md` (outcome and requirements), `plan.md` (architecture, interfaces and reuse), `test-spec.md` (acceptance and quality proof), `tasks.md` (implementation order), and `status.json` (delivery and acceptance state). The files stand alone for public contributors; draft notes and private infrastructure are not prerequisites.

| ID | Feature | State |
| --- | --- | --- |
| [EH-707](leveraged-trading-guide/spec.md) | Leveraged trading guide, gold example, skill and explainer contract | SPECIFIED / NOT_AUDITED |
| [EH-708](finance-media-intake/spec.md) | Finance media evidence intake and strategy linkage | SPECIFIED / NOT_AUDITED |

`SPECIFIED` means a build contract exists. `BUILDING`, `BUILT`, `LANDED`, `CLOSED`, `DEFERRED`, `REJECTED`, and `UNKNOWN` describe delivery; `NOT_AUDITED`, `PENDING`, `ACCEPTED`, and `FAILED` describe acceptance independently. `LANDED` needs an owner-repository merged commit; `ACCEPTED` also needs the test and consumer receipts. Do not infer implementation from documentation.

Cross-repository owners: [epistemic-graph](https://github.com/Knuckles-Team/epistemic-graph/tree/main/specs) owns finance ontology, strategy evaluation, backtests and leverage math; [media-downloader](https://github.com/Knuckles-Team/media-downloader) owns caption/frame capture; [agent-webui](https://github.com/Knuckles-Team/agent-webui/tree/main/specs/finance-asset-manager) owns browser presentation; Emerald owns the derived finance skill, guide and governed effect boundary. Contributors may use [universal-skills](https://github.com/Knuckles-Team/universal-skills) spec-generator, spec-verifier and task-planner with [graph-os-development](https://github.com/Knuckles-Team/graph-os/tree/main/graph_os/skills/graph-os-development) to provision and navigate the ecosystem.
