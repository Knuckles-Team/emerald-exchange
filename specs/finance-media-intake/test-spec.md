# EMERALD-MEDIA — Test specification

| Case | Fixture/action | Expected result |
| --- | --- | --- |
| MEDIA-T1 | Four video URLs with `subtitle_languages="en"` and direct article read | Five source receipts; exact URLs, capture times, digest/availability and English-only request recorded |
| MEDIA-T2 | Complete captions and frames, caption-only bundle, missing captions, failed download | Distinct statuses; no frame claim from caption-only evidence; ASR fallback labeled; failed source remains pending |
| MEDIA-T3 | Transcript claim contradicts an on-screen step or another source | Conflict recorded with timestamps and supersession decision; not silently merged |
| MEDIA-T4 | Extract a DCA schedule/amount rule and a gold leverage rule | Each links to real versioned EG `StrategySpec` or `UNMAPPED`; skill parser/catalog accepts the output |
| MEDIA-T5 | Untested claim, failed/old backtest, missing cost, version mismatch, thin history | No recommendation promotion; explicit abstention or pending evidence |
| MEDIA-T6 | Backtest passes required statistics, costs and out-of-sample validation | Informational recommendation may cite strategy, version, run and limitations; no order effect |
| MEDIA-T7 | Re-ingest same URL/revision; source updates later | Idempotent unchanged skill or reviewed revision with prior claims traceable; no duplicate skill sprawl |
| MEDIA-T8 | Attempt to drive `mcp_orders` from a new skill | Refused; existing RiskGuard and approval boundary remain authoritative |

Acceptance needs actual capture receipts, reviewer signoff, skill/catalog validation, EG/AU consumer checks and an exact merged revision. Run configured repo lint/types/tests; for executable changes, include CCCC, jscpd, Dupehound and KISS results. Record unavailable tools as unresolved. Do not claim the videos were watched or the skills were built from this spec alone.

## Rows awaiting bound tests
- `EMERALD-MEDIA-R001`: planned proof `tests/test_media_intake_contract.py::test_unmapped_rule_cannot_drive_recommendation`. Expected: A rule mapped to a strategy link produces the recommendation and the capture log separates source from claim.. Refusal: An unmapped rule is refused and no recommendation is produced..
