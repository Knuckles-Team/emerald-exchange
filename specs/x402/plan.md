# CONN-EMERALD-EXCHANGE-X402 — Design and implementation plan

Governing spec: [spec.md](spec.md).

## Existing system and reuse

Wallet, signing, attribution, RLUSD payment, spending limits and the kill-switch live in the XRPL spec rows of this repository. The x402 work adds only the protocol layer: the typed models, the loop, the settlement mapping, the skill reference and the prompts. No second wallet path exists.

## Architecture

A new `emerald_exchange/` module wraps the XRPL backend. It calls the x402-enabled endpoint, reads the 402 payment requirement, settles in RLUSD through the XRPL payment path, and retries once with the payment proof. The Coinbase agentic-wallet skill content is a reference entry in the skill surface. The connector stores the reference and its freshness check; the upstream content does not ship here.

## Interfaces and data model

MCP tools: `x402_purchase` and `x402_status`. Models: intent, payment requirement, payment proof, settlement result. Prompts: x402 purchase, spending-limit check.

## Live integration path

`x402_purchase` calls the x402 module, which calls the XRPL payment path for the RLUSD settlement, then the ledger, then the retry with the proof. The risk guard sits on the XRPL side of the edge; x402 adds no second check.

## Quality and release gates

Repository pre-commit stage on changed files. x402 tests run against a fixture endpoint and the test network.

## Risks, alternatives, and decisions

Decision: reference the Coinbase skill content instead of vendoring it; a vendored copy drifts from upstream. Decision: settle in RLUSD through the existing XRPL path; a second wallet stack is a non-goal. Risk: upstream endpoint contract changes; the typed model fails validation instead of guessing.

## Amendments

- None yet.
