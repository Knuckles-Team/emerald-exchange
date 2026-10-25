# CONN-EMERALD-EXCHANGE-X402 — Implementation tasks

Governing spec: [spec.md](spec.md). Design: [plan.md](plan.md). Rows: [requirements.md](requirements.md).

- [ ] **CONN-EMERALD-EXCHANGE-X402-R001:** Wire the x402 intent, payment requirement and payment proof models with validation.
- [ ] **CONN-EMERALD-EXCHANGE-X402-R002:** Wire the pay-and-retry loop with one proof-bearing retry and refusal surfacing.
- [ ] **CONN-EMERALD-EXCHANGE-X402-R003:** Expose the Coinbase agentic-wallet skill as a referenced connector skill with a drift check.
- [ ] **CONN-EMERALD-EXCHANGE-X402-R004:** Settle x402 payments in RLUSD through the XRPL payment path.
- [ ] **CONN-EMERALD-EXCHANGE-X402-R005:** Reuse the XRPL wallet and signing rows for all x402 payment calls.
- [ ] **CONN-EMERALD-EXCHANGE-X402-R006:** Route x402 payments through the XRPL attribution, spending-limit check and kill-switch.
- [ ] **CONN-EMERALD-EXCHANGE-X402-R007:** Package the x402 purchase and spending-limit-check prompts.
