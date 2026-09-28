# Emerald Exchange constitution

Status: PROPOSED. Drafted: 2026-09-28. Version: 0.1.0. Specification index: [specs/README.md](../../specs/README.md).

## I. One owner and existing wiring

Emerald owns provider transport, finance skills and governed trading effects. A change must trace its live entrypoint through the existing backend factory, MCP tool, execution bridge and risk guard where applicable. Reuse the legal owner and delete superseded paths. Epistemic Graph owns numeric finance and strategy evaluation; media-downloader owns capture; WebUI owns browser presentation. Do not create another authority for the same data, calculation or order policy.

## II. Complete public specs

Build contracts live in `specs/<feature>/`: `spec.md` states observable behavior; `plan.md` describes architecture, data, security, failure and reuse; `test-spec.md` names positive and negative proof; `tasks.md` orders implementation; `status.json` records delivery and acceptance separately. Public specs stand alone and cite only public repository contracts. Historical `.specify/specs/` records are legacy drafts until distilled into this structure; `.specify/` holds project configuration and this constitution.

## III. Finance safety and evidence

Paper is the default. A signal, media claim, guide or explainer never authorizes an order. Every order uses the existing governed path and `RiskGuard.pre_trade_check()`; live leveraged execution also requires explicit per-instrument policy and approved lease. Claim-derived recommendations require versioned strategy and backtest evidence and must abstain when evidence is insufficient. Numeric finance work belongs in Epistemic Graph.

## IV. Quality and acceptance

Apply the repository's language-native checks and relevant CCCC, jscpd, Dupehound and KISS review to changed executable code. Do not invent scanner thresholds or passing receipts. Tests prove the real consumer path, denied effects, failures and recovery where relevant. `LANDED` requires an exact merged owner revision; `ACCEPTED` requires the specified tests and consumer/release receipts. Documentation presence alone proves neither.

## V. Amendment

Revise this constitution in a reviewed change that identifies the affected contracts and migration impact. Keep the public spec index and templates aligned with the adopted structure.
