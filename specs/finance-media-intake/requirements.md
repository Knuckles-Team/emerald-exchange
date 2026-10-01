# EMERALD-MEDIA-001 requirements

Every requirement this specification owns, with the proof that closes it. Delivery state and
public evidence for each ID are recorded in [`status.json`](status.json); this file defines what
each ID means. The design is in [`spec.md`](spec.md) and [`plan.md`](plan.md), the test contract
in [`test-spec.md`](test-spec.md), and the work order in [`tasks.md`](tasks.md).

| ID | Requirement | Verification |
|---|---|---|
| `EMERALD-MEDIA-R001` | **Finance media intake into reviewable Emerald skills.** Designated dollar-cost-averaging and gold/leverage media sources are captured with their public source URL and capture time via media-watch, with English captions requested explicitly (`en`), and the resulting Emerald skills separate source-demonstrated steps from source claims while linking each mechanical trading rule to a versioned StrategySpec ID or marking it UNMAPPED. | A capture-log fixture and a reviewer sample confirm source/claim separation and StrategySpec linkage, backed by a contract test that blocks any UNMAPPED rule from driving a recommendation. |
