# CONN-EMERALD-EXCHANGE-X402 — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-EMERALD-EXCHANGE-X402-R001` | `tests/test_x402_model.py::test_intent_resource_pricing_models` | The request, 402 payment requirement and payment proof validate as stable models. |
| T-002 | `CONN-EMERALD-EXCHANGE-X402-R002` | `tests/test_x402_pay_retry.py::test_pay_and_retry_loop` | The loop pays on the 402 requirement, retries once with the proof, and surfaces the resource or the refusal. |
| T-003 | `CONN-EMERALD-EXCHANGE-X402-R003` | `tests/test_x402_skill.py::test_coinbase_skill_reference_not_vendored` | The Coinbase agentic-wallet skill resolves as a reference; no upstream content ships in the package. |
| T-004 | `CONN-EMERALD-EXCHANGE-X402-R004` | `tests/test_x402_rusd.py::test_rusd_settlement` | The x402 payment settles in RLUSD through the XRPL path and reports the ledger result. |
| T-005 | `CONN-EMERALD-EXCHANGE-X402-R005` | `tests/test_x402_composition.py::test_wallet_signing_reuses_xrpl` | The x402 payment call enters the XRPL wallet and signing path; no second wallet exists. |
| T-006 | `CONN-EMERALD-EXCHANGE-X402-R006` | `tests/test_x402_risk.py::test_shared_attribution_and_spend_caps` | The x402 payment carries the XRPL attribution and refuses over the XRPL spending limit or kill-switch. |
| T-007 | `CONN-EMERALD-EXCHANGE-X402-R007` | `tests/test_x402_prompts.py::test_x402_prompts_list` | The x402 purchase and spending-limit-check prompts appear in the prompt listing. |

## Negative and boundary cases

- Second 402 after the first retry: the loop stops and surfaces the refusal reason.
- Payment requirement names a non-RLUSD currency: the loop refuses.
- Upstream skill reference moves: the freshness check reports drift instead of serving stale content.
- Kill-switch active: the x402 purchase refuses before it pays.

## Quality and release proof

Repository pre-commit stage on changed files, the focused x402 tests against the fixture endpoint and the test network, `tests/test_public_specs.py`, and the spec-standard and spec-status checks from the pipelines hooks.
