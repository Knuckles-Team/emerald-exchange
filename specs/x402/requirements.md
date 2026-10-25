# CONN-EMERALD-EXCHANGE-X402 — Requirements

Governing spec: [spec.md](spec.md).

Each row is one requirement. A row names the file it touches and the test that proves it. The generator sets each row's state in `status.json`.

| ID | Requirement | Acceptance |
|---|---|---|
| `CONN-EMERALD-EXCHANGE-X402-R001` | **x402 intent, resource and pricing model.** The connector types the x402 request, the 402 payment requirement response and the payment proof as stable validated models. | `tests/test_x402_model.py::test_intent_resource_pricing_models` |
| `CONN-EMERALD-EXCHANGE-X402-R002` | **Pay-and-retry loop.** The connector calls an x402-enabled endpoint, reads the 402 payment requirement, pays, retries once with the payment proof, and surfaces the resource or the refusal reason. | `tests/test_x402_pay_retry.py::test_pay_and_retry_loop` |
| `CONN-EMERALD-EXCHANGE-X402-R003` | **Coinbase agentic-wallet skill, referenced.** The connector exposes the Coinbase agentic-wallet skill as a connector skill whose content is referenced from the upstream source, not vendored. A freshness check reports reference drift. | `tests/test_x402_skill.py::test_coinbase_skill_reference_not_vendored` |
| `CONN-EMERALD-EXCHANGE-X402-R004` | **RLUSD settlement.** x402 payments settle in RLUSD through the XRPL RLUSD payment path. The settlement reports the ledger result. Depends-on: `CONN-EMERALD-EXCHANGE-XRPL-R002`. | `tests/test_x402_rusd.py::test_rusd_settlement` |
| `CONN-EMERALD-EXCHANGE-X402-R005` | **Cross-chain composition with XRPL.** Wallet and signing reuse the XRPL spec rows instead of a second wallet path. This row is a child slice of the XRPL wallet row. Depends-on: `CONN-EMERALD-EXCHANGE-XRPL-R001`, `CONN-EMERALD-EXCHANGE-XRPL-R007`. | `tests/test_x402_composition.py::test_wallet_signing_reuses_xrpl` |
| `CONN-EMERALD-EXCHANGE-X402-R006` | **Shared attribution and spend caps.** Every x402 payment carries the XRPL agent attribution and passes the XRPL spending-limit check and kill-switch. Depends-on: `CONN-EMERALD-EXCHANGE-XRPL-R008`. | `tests/test_x402_risk.py::test_shared_attribution_and_spend_caps` |
| `CONN-EMERALD-EXCHANGE-X402-R007` | **Prompts.** The connector packages the x402 purchase and spending-limit-check prompts. | `tests/test_x402_prompts.py::test_x402_prompts_list` |
