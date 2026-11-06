# CONN-EMERALD-EXCHANGE-X402 — x402 pay-and-retry with Coinbase agent-wallet skill flavor

Owner: emerald-exchange. Cross-repo IDs: `CONN-EMERALD-EXCHANGE-XRPL-R001`, `CONN-EMERALD-EXCHANGE-XRPL-R002`, `CONN-EMERALD-EXCHANGE-XRPL-R007`, `CONN-EMERALD-EXCHANGE-XRPL-R008` in [specs/xrpl](../xrpl/spec.md) of this repository.

## Purpose and user stories

An agent buys from an x402-enabled endpoint. It reads the payment requirement the endpoint returns, pays through the shared XRPL wallet path, retries with the payment proof, and lands on the resource. The Coinbase agentic-wallet skill ships as referenced connector skill content, not a vendored copy.

## Why a new spec

Search of `specs/`: no spec owns the x402 pay-and-retry loop or the agent-wallet skill provisioning. The XRPL rows this spec reuses live in `CONN-EMERALD-EXCHANGE-XRPL` in this repository. x402 and Coinbase are new external surfaces for this connector, so the capability gets its own spec.

## Scope and interfaces

Owned: the x402 intent, resource and pricing model; the pay-and-retry loop; RLUSD settlement; the referenced Coinbase agentic-wallet skill; attribution and spend caps shared with the XRPL risk constraints; and the x402 prompts. Rows R008 to R014 extend the spec to the whole agent payment domain: the `payments` tool domain, rail and wallet-provider seams, shared governance, the optional extra, the paper-first rail and the payments skill. The routing and the wallet decision are in [research.md](research.md). Non-goals: hosting x402 endpoints, a second wallet stack, and any payment path that bypasses the XRPL signing and risk controls.

## Open questions

- Which Linux-capable wallet provider ships first (R011). Open owner decision; options and recommendation in [research.md](research.md).
- The skill stays referenced, never vendored; upstream drift reports instead of forking.

## User Scenarios & Testing

### User Story 1 - x402 pay-and-retry with Coinbase agent-wallet skill flavor (Priority: P1)

An agent buys from an x402-enabled endpoint. It reads the payment requirement the endpoint returns, pays through the shared XRPL wallet path, retries with the payment proof, and lands on the resource. The Coinbase agentic-wallet skill ships as referenced connector skill content, not a vendored copy.

**Acceptance Scenarios**:

1. **Given** the connector is configured, **When** the behaviour of row `CONN-EMERALD-EXCHANGE-X402-R001` (x402 intent, resource and pricing model) is exercised, **Then** x402 intent, resource and pricing model.
2. **Given** the connector is configured, **When** the behaviour of row `CONN-EMERALD-EXCHANGE-X402-R002` (pay-and-retry loop) is exercised, **Then** pay-and-retry loop.
3. **Given** the connector is configured, **When** the behaviour of row `CONN-EMERALD-EXCHANGE-X402-R003` (agentic-wallet skill, referenced) is exercised, **Then** agentic-wallet skill, referenced.

### Edge Cases

- If `CONN-EMERALD-EXCHANGE-X402-R001` is not met, its proving test fails: x402 intent, resource and pricing model.
- If `CONN-EMERALD-EXCHANGE-X402-R002` is not met, its proving test fails: pay-and-retry loop.
- If `CONN-EMERALD-EXCHANGE-X402-R003` is not met, its proving test fails: agentic-wallet skill, referenced.

## Requirements

- **FR-001**: x402 intent, resource and pricing model. Rows: `CONN-EMERALD-EXCHANGE-X402-R001`.
- **FR-002**: Pay-and-retry loop. Rows: `CONN-EMERALD-EXCHANGE-X402-R002`.
- **FR-003**: Agentic-wallet skill, referenced. Rows: `CONN-EMERALD-EXCHANGE-X402-R003`.
- **FR-004**: RLUSD settlement. Rows: `CONN-EMERALD-EXCHANGE-X402-R004`.
- **FR-005**: Cross-chain composition with XRPL. Rows: `CONN-EMERALD-EXCHANGE-X402-R005`.
- **FR-006**: Shared attribution and spend caps. Rows: `CONN-EMERALD-EXCHANGE-X402-R006`.
- **FR-007**: Prompts. Rows: `CONN-EMERALD-EXCHANGE-X402-R007`.
- **FR-008**: Payments tool domain. Rows: `CONN-EMERALD-EXCHANGE-X402-R008`.
- **FR-009**: Payment rail seam. Rows: `CONN-EMERALD-EXCHANGE-X402-R009`.
- **FR-010**: Payment governance reuses the existing hardening. Rows: `CONN-EMERALD-EXCHANGE-X402-R010`.
- **FR-011**: Wallet provider seam, Linux-capable. Rows: `CONN-EMERALD-EXCHANGE-X402-R011`.
- **FR-012**: Optional payments extra. Rows: `CONN-EMERALD-EXCHANGE-X402-R012`.
- **FR-013**: Paper-first payment rail. Rows: `CONN-EMERALD-EXCHANGE-X402-R013`.
- **FR-014**: Payments skill content. Rows: `CONN-EMERALD-EXCHANGE-X402-R014`.

## Success Criteria

- **SC-001**: X402 intent, resource and pricing model. Rows: `CONN-EMERALD-EXCHANGE-X402-R001`.
- **SC-002**: Pay-and-retry loop. Rows: `CONN-EMERALD-EXCHANGE-X402-R002`.
- **SC-003**: Agentic-wallet skill, referenced. Rows: `CONN-EMERALD-EXCHANGE-X402-R003`.
- **SC-004**: RLUSD settlement. Rows: `CONN-EMERALD-EXCHANGE-X402-R004`.
- **SC-005**: Cross-chain composition with XRPL. Rows: `CONN-EMERALD-EXCHANGE-X402-R005`.
- **SC-006**: Shared attribution and spend caps. Rows: `CONN-EMERALD-EXCHANGE-X402-R006`.
- **SC-007**: Prompts. Rows: `CONN-EMERALD-EXCHANGE-X402-R007`.
- **SC-008**: Payments tool domain. Rows: `CONN-EMERALD-EXCHANGE-X402-R008`.
- **SC-009**: Payment rail seam. Rows: `CONN-EMERALD-EXCHANGE-X402-R009`.
- **SC-010**: Payment governance reuses the existing hardening. Rows: `CONN-EMERALD-EXCHANGE-X402-R010`.
- **SC-011**: Wallet provider seam, Linux-capable. Rows: `CONN-EMERALD-EXCHANGE-X402-R011`.
- **SC-012**: Optional payments extra. Rows: `CONN-EMERALD-EXCHANGE-X402-R012`.
- **SC-013**: Paper-first payment rail. Rows: `CONN-EMERALD-EXCHANGE-X402-R013`.
- **SC-014**: Payments skill content. Rows: `CONN-EMERALD-EXCHANGE-X402-R014`.

## Assumptions

- The external system is reachable with operator-supplied credentials.
- The SDK and engine contracts the rows cite are at the floors declared in `pyproject.toml`.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `CONN-EMERALD-EXCHANGE-X402-R001` | [plan.md](plan.md) | T-001 | [test-spec.md](test-spec.md) |
| FR-002 | `CONN-EMERALD-EXCHANGE-X402-R002` | [plan.md](plan.md) | T-002 | [test-spec.md](test-spec.md) |
| FR-003 | `CONN-EMERALD-EXCHANGE-X402-R003` | [plan.md](plan.md) | T-003 | [test-spec.md](test-spec.md) |
| FR-004 | `CONN-EMERALD-EXCHANGE-X402-R004` | [plan.md](plan.md) | T-004 | [test-spec.md](test-spec.md) |
| FR-005 | `CONN-EMERALD-EXCHANGE-X402-R005` | [plan.md](plan.md) | T-005 | [test-spec.md](test-spec.md) |
| FR-006 | `CONN-EMERALD-EXCHANGE-X402-R006` | [plan.md](plan.md) | T-006 | [test-spec.md](test-spec.md) |
| FR-007 | `CONN-EMERALD-EXCHANGE-X402-R007` | [plan.md](plan.md) | T-007 | [test-spec.md](test-spec.md) |
| FR-008 | `CONN-EMERALD-EXCHANGE-X402-R008` | [plan.md](plan.md) | T-008 | [test-spec.md](test-spec.md) |
| FR-009 | `CONN-EMERALD-EXCHANGE-X402-R009` | [plan.md](plan.md) | T-009 | [test-spec.md](test-spec.md) |
| FR-010 | `CONN-EMERALD-EXCHANGE-X402-R010` | [plan.md](plan.md) | T-010 | [test-spec.md](test-spec.md) |
| FR-011 | `CONN-EMERALD-EXCHANGE-X402-R011` | [plan.md](plan.md) | T-011 | [test-spec.md](test-spec.md) |
| FR-012 | `CONN-EMERALD-EXCHANGE-X402-R012` | [plan.md](plan.md) | T-012 | [test-spec.md](test-spec.md) |
| FR-013 | `CONN-EMERALD-EXCHANGE-X402-R013` | [plan.md](plan.md) | T-013 | [test-spec.md](test-spec.md) |
| FR-014 | `CONN-EMERALD-EXCHANGE-X402-R014` | [plan.md](plan.md) | T-014 | [test-spec.md](test-spec.md) |
