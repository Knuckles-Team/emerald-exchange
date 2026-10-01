# EMERALD-GUIDE-001 — Test specification

| Case | Fixture/action | Expected result |
| --- | --- | --- |
| GUIDE-T1 | Fixed gold futures and security examples with quantity, multiplier, fees, initial/maintenance terms, adverse and gap moves | Published arithmetic matches independently calculated expected values and EG-FINANCE-PRIMITIVES-R010 response; units/currency explicit |
| GUIDE-T2 | Missing, expired or jurisdiction-ineligible terms; EG unavailable | No numeric liquidation claim or fallback guess; reason and source state visible |
| GUIDE-T3 | Standard/micro futures, margin security, daily-reset ETF and FX sections | Required distinct mechanics and risk disclosures pass editorial matrix; no category conflation |
| GUIDE-T4 | Render public guide, skill and WebUI content from same revision | IDs, version, sources and reviewed date match; accessible headings/links work |
| GUIDE-T5 | Click explainer or ingest an untested video claim | No order submission, signal promotion or recommendation; paper simulation remains read only |
| GUIDE-T6 | Attempt live leveraged order without instrument policy, approver lease or guard approval | Existing governed path refuses it; no explainer bypass exists |
| GUIDE-T7 | Primary source revises contract/margin terms | Publication is held until source card and fixture are reviewed and content revision advanced |

Use static link/content checks, skill parser checks, EG contract tests and WebUI consumer tests. Record exact revision, fixtures, source retrieval dates and results in public receipts. For code changes run repository lint/types/tests plus configured CCCC, jscpd and Dupehound; report absent tool/threshold as an unresolved gate, not a pass. KISS review confirms no duplicate numerical engine or order route. Documentation publication alone cannot mark EMERALD-GUIDE-R001 accepted.
