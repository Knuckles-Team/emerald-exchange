# CONN-EMERALD-EXCHANGE-X402 — Test specification

Governing spec: [spec.md](spec.md).

| Test ID | Requirement | Proving test | Expected observation |
|---|---|---|---|
| T-001 | `CONN-EMERALD-EXCHANGE-X402-R001` | `tests/test_x402_model.py::test_intent_resource_pricing_models` (planned) | The request, 402 payment requirement and payment proof validate as stable models. |
| T-002 | `CONN-EMERALD-EXCHANGE-X402-R002` | `tests/test_x402_pay_retry.py::test_pay_and_retry_loop` (planned) | The loop pays on the 402 requirement, retries once with the proof, and surfaces the resource or the refusal. |
| T-003 | `CONN-EMERALD-EXCHANGE-X402-R003` | `tests/test_x402_skill.py::test_coinbase_skill_reference_not_vendored` (planned) | The Coinbase agentic-wallet skill resolves as a reference; no upstream content ships in the package. |
| T-004 | `CONN-EMERALD-EXCHANGE-X402-R004` | `tests/test_x402_rusd.py::test_rusd_settlement` (planned) | The x402 payment settles in RLUSD through the XRPL path and reports the ledger result. |
| T-005 | `CONN-EMERALD-EXCHANGE-X402-R005` | `tests/test_x402_composition.py::test_wallet_signing_reuses_xrpl` (planned) | The x402 payment call enters the XRPL wallet and signing path; no second wallet exists. |
| T-006 | `CONN-EMERALD-EXCHANGE-X402-R006` | `tests/test_x402_risk.py::test_shared_attribution_and_spend_caps` (planned) | The x402 payment carries the XRPL attribution and refuses over the XRPL spending limit or kill-switch. |
| T-007 | `CONN-EMERALD-EXCHANGE-X402-R007` | `tests/test_x402_prompts.py::test_x402_prompts_list` (planned) | The x402 purchase and spending-limit-check prompts appear in the prompt listing. |
| T-008 | `CONN-EMERALD-EXCHANGE-X402-R008` | `tests/test_payments_tools.py::test_one_typed_tool_per_operation` (planned) | Every payments tool is listed once, reads are read-only, and a send reaches the active rail only through the governor. |
| T-009 | `CONN-EMERALD-EXCHANGE-X402-R009` | `tests/test_payment_rails.py::test_rails_register_and_send_names_rail` (planned) | Two registered rails (ledger and stablecoin) are listed, and a send names its rail explicitly. |
| T-010 | `CONN-EMERALD-EXCHANGE-X402-R010` | `tests/test_payment_governor.py::test_limits_halt_breaker_and_approval` (planned) | The governor refuses at the limit, on halt, on a tripped breaker and above the approval threshold, and the XRPL path now gives the same refusals through the same governor. |
| T-011 | `CONN-EMERALD-EXCHANGE-X402-R011` | `tests/test_payment_wallet_provider.py::test_unset_refuses_and_no_key_material_leaks` (planned) | With no provider set a send refuses; with a stub provider the address resolves and no key material appears in any result or log. |
| T-012 | `CONN-EMERALD-EXCHANGE-X402-R012` | `tests/test_payments_extra_optional.py::test_base_install_imports_without_payment_libraries` (planned) | A base install imports cleanly without the payment libraries and the payments tools refuse with the extra-missing code. |
| T-013 | `CONN-EMERALD-EXCHANGE-X402-R013` | `tests/test_paper_payment_rail.py::test_default_send_is_simulated` (planned) | The default send returns a simulated receipt with no signing and no network call, and live mode needs the stage and opt-in. |
| T-014 | `CONN-EMERALD-EXCHANGE-X402-R014` | `tests/test_payments_skill.py::test_payments_skill_lists_and_names_real_tools` (planned) | The skill resolves from the connector, names only registered tools, and the package holds no upstream skill text. |

## Negative and boundary cases

- Second 402 after the first retry: the loop stops and surfaces the refusal reason.
- Payment requirement names a non-RLUSD currency: the loop refuses.
- Upstream skill reference moves: the freshness check reports drift instead of serving stale content.
- Kill-switch active: the x402 purchase refuses before it pays.

## Quality and release proof

Repository pre-commit stage on changed files, the focused x402 tests against the fixture endpoint and the test network, `tests/test_public_specs.py`, and the spec-standard and spec-status checks from the pipelines hooks.
