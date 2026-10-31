# EMERALD-GUIDE requirements

Every requirement this specification owns, with the proof that closes it. Delivery state and
public evidence for each ID are recorded in [`status.json`](status.json); this file defines what
each ID means. The design is in [`spec.md`](spec.md) and [`plan.md`](plan.md), the test contract
in [`test-spec.md`](test-spec.md), and the work order in [`tasks.md`](tasks.md).

| ID | Requirement | Verification |
|---|---|---|
| `EMERALD-GUIDE-R001` | **Leveraged trading guide across docs, skill, and explainer.** Stage: content parity. Callers: the docs build (`mkdocs.yml` page `docs/leveraged-trading-guide.md`) and the skill provider. The provider serves `skill://emerald-exchange-leveraged-trading` from `emerald_exchange/skills/emerald-exchange-leveraged-trading/SKILL.md`. The arbora projection `finance.guide.get` (ARBORA-DATA-MARKET-R003.15) feeds the WebUI explainer. Rule: one guide source carries `guide_id` `EMERALD-GUIDE-R001`, a semantic `revision`, `reviewed_at`, `reviewer` and source cards. The three projections carry identical values. The guide draws on EMERALD-MEDIA-R001 intake, current exchange specifications, FINRA and Reg T rules, and CFTC rules. The worked gold example uses a fixed illustrative fixture with decimal-string amounts; it quotes no live price. Its margin and loss figures come from the margin module EG-FINANCE-PRIMITIVES-R010. The guide stores the verified output reference and holds no formula. Writes: none. Depends on: EMERALD-MEDIA-R001, EG-FINANCE-PRIMITIVES-R010. | Test: `tests/test_guide_parity.py::test_docs_skill_and_projection_carry_identical_revision_metadata` (L2) compares the three. `::test_example_figures_match_recorded_engine_reply` (L3) replays a recorded engine reply. |
