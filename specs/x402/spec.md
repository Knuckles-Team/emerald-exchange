# CONN-EMERALD-EXCHANGE-X402 — x402 pay-and-retry with Coinbase agent-wallet skill flavor

Owner: emerald-exchange. Cross-repo IDs: `CONN-EMERALD-EXCHANGE-XRPL-R001`, `CONN-EMERALD-EXCHANGE-XRPL-R002`, `CONN-EMERALD-EXCHANGE-XRPL-R007`, `CONN-EMERALD-EXCHANGE-XRPL-R008` in [specs/xrpl](../xrpl/spec.md) of this repository.

## Purpose and user stories

An agent buys from an x402-enabled endpoint. It reads the payment requirement the endpoint returns, pays through the shared XRPL wallet path, retries with the payment proof, and lands on the resource. The Coinbase agentic-wallet skill ships as referenced connector skill content, not a vendored copy.

## Requirements and acceptance

See [requirements.md](requirements.md) for the definition of every requirement ID this spec owns and [status.json](status.json) for their current delivery and acceptance state.

## Why a new spec

Search of `specs/`: no spec owns the x402 pay-and-retry loop or the agent-wallet skill provisioning. The XRPL rows this spec reuses live in `CONN-EMERALD-EXCHANGE-XRPL` in this repository. x402 and Coinbase are new external surfaces for this connector, so the capability gets its own spec.

## Scope and interfaces

Owned: the x402 intent, resource and pricing model; the pay-and-retry loop; RLUSD settlement; the referenced Coinbase agentic-wallet skill; attribution and spend caps shared with the XRPL risk constraints; and the x402 prompts. Non-goals: hosting x402 endpoints, a second wallet stack, and any payment path that bypasses the XRPL signing and risk controls.

## Open questions

- None. The skill stays referenced, never vendored; upstream drift reports instead of forking.
