# CONN-EMERALD-EXCHANGE-XRPL — XRPL agent wallet, payments and trading

Owner: emerald-exchange. Cross-repo IDs: none.

## Purpose and user stories

An agent runs a wallet on the XRPL network. It moves XRP and RLUSD, escrows funds for gated work, trades on the native DEX, and answers account and portfolio queries. Every agent-initiated transaction carries attribution, passes the spending-limit check, and previews before it signs. The wallet defaults to the test network; production needs an explicit opt-in.

## Why a new spec

Search of `specs/`: `EMERALD-OPS` owns read-only exchange operations on the existing backends, `EMERALD-GUIDE` owns the leveraged trading guide, `EMERALD-MEDIA` owns finance media intake, and `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT` owns the packaged content surface. None owns the XRPL network: its wallets, payments, trust lines, escrow, DEX, attribution, or risk controls. XRPL is a new external system for this connector, so the capability gets its own spec.

## Scope and interfaces

Owned: wallet create, load and sign; XRP and RLUSD payments; trust lines; escrow-gated work; native DEX and AMM market operations; account and portfolio queries; SourceTag and Memo attribution; spending limits and kill-switch; and the docs, network endpoint, fee schedule and live status resources. The MCP server serves these through the existing `emerald-exchange-mcp` connector surface, the existing skill and prompt packaging, and the ontology pack.

Non-goals: custody for other networks, a second payment stack, and any order path that bypasses the existing risk guard and execution bridge.

## Open questions

- None. Production opt-in is a future requirements row, not a silent default.

## User Scenarios & Testing

### User Story 1 - XRPL agent wallet, payments and trading (Priority: P1)

An agent runs a wallet on the XRPL network. It moves XRP and RLUSD, escrows funds for gated work, trades on the native DEX, and answers account and portfolio queries. Every agent-initiated transaction carries attribution, passes the spending-limit check, and previews before it signs. The wallet defaults to the test network; production needs an explicit opt-in.

**Acceptance Scenarios**:

1. **Given** the connector is configured, **When** the behaviour of row `CONN-EMERALD-EXCHANGE-XRPL-R001` (agent wallet create, load and sign) is exercised, **Then** agent wallet create, load and sign.
2. **Given** the connector is configured, **When** the behaviour of row `CONN-EMERALD-EXCHANGE-XRPL-R002` (xrp and rlusd payments) is exercised, **Then** xRP and RLUSD payments.
3. **Given** the connector is configured, **When** the behaviour of row `CONN-EMERALD-EXCHANGE-XRPL-R003` (trust lines) is exercised, **Then** trust lines.

### Edge Cases

- If `CONN-EMERALD-EXCHANGE-XRPL-R001` is not met, its proving test fails: agent wallet create, load and sign.
- If `CONN-EMERALD-EXCHANGE-XRPL-R002` is not met, its proving test fails: xrp and rlusd payments.
- If `CONN-EMERALD-EXCHANGE-XRPL-R003` is not met, its proving test fails: trust lines.

## Requirements

- **FR-001**: Agent wallet create, load and sign. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R001`.
- **FR-002**: XRP and RLUSD payments. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R002`.
- **FR-003**: Trust lines. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R003`.
- **FR-004**: Escrow-gated work. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R004`.
- **FR-005**: Native DEX and AMM market operations. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R005`.
- **FR-006**: Account and portfolio queries. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R006`.
- **FR-007**: Agent attribution and audit trail. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R007`.
- **FR-008**: Spending-limit checks and kill-switch. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R008`.
- **FR-009**: Safety defaults. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R009`.
- **FR-010**: Resource serving. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R010`.
- **FR-011**: Prompts. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R011`.
- **FR-012**: Skills. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R012`.
- **FR-013**: Ontology content. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R013`.

## Success Criteria

- **SC-001**: Agent wallet create, load and sign. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R001`.
- **SC-002**: XRP and RLUSD payments. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R002`.
- **SC-003**: Trust lines. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R003`.
- **SC-004**: Escrow-gated work. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R004`.
- **SC-005**: Native DEX and AMM market operations. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R005`.
- **SC-006**: Account and portfolio queries. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R006`.
- **SC-007**: Agent attribution and audit trail. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R007`.
- **SC-008**: Spending-limit checks and kill-switch. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R008`.
- **SC-009**: Safety defaults. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R009`.
- **SC-010**: Resource serving. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R010`.
- **SC-011**: Prompts. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R011`.
- **SC-012**: Skills. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R012`.
- **SC-013**: Ontology content. Rows: `CONN-EMERALD-EXCHANGE-XRPL-R013`.

## Assumptions

- The external system is reachable with operator-supplied credentials.
- The SDK and engine contracts the rows cite are at the floors declared in `pyproject.toml`.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `CONN-EMERALD-EXCHANGE-XRPL-R001` | [plan.md](plan.md) | T-001 | [test-spec.md](test-spec.md) |
| FR-002 | `CONN-EMERALD-EXCHANGE-XRPL-R002` | [plan.md](plan.md) | T-002 | [test-spec.md](test-spec.md) |
| FR-003 | `CONN-EMERALD-EXCHANGE-XRPL-R003` | [plan.md](plan.md) | T-003 | [test-spec.md](test-spec.md) |
| FR-004 | `CONN-EMERALD-EXCHANGE-XRPL-R004` | [plan.md](plan.md) | T-004 | [test-spec.md](test-spec.md) |
| FR-005 | `CONN-EMERALD-EXCHANGE-XRPL-R005` | [plan.md](plan.md) | T-005 | [test-spec.md](test-spec.md) |
| FR-006 | `CONN-EMERALD-EXCHANGE-XRPL-R006` | [plan.md](plan.md) | T-006 | [test-spec.md](test-spec.md) |
| FR-007 | `CONN-EMERALD-EXCHANGE-XRPL-R007` | [plan.md](plan.md) | T-007 | [test-spec.md](test-spec.md) |
| FR-008 | `CONN-EMERALD-EXCHANGE-XRPL-R008` | [plan.md](plan.md) | T-008 | [test-spec.md](test-spec.md) |
| FR-009 | `CONN-EMERALD-EXCHANGE-XRPL-R009` | [plan.md](plan.md) | T-009 | [test-spec.md](test-spec.md) |
| FR-010 | `CONN-EMERALD-EXCHANGE-XRPL-R010` | [plan.md](plan.md) | T-010 | [test-spec.md](test-spec.md) |
| FR-011 | `CONN-EMERALD-EXCHANGE-XRPL-R011` | [plan.md](plan.md) | T-011 | [test-spec.md](test-spec.md) |
| FR-012 | `CONN-EMERALD-EXCHANGE-XRPL-R012` | [plan.md](plan.md) | T-012 | [test-spec.md](test-spec.md) |
| FR-013 | `CONN-EMERALD-EXCHANGE-XRPL-R013` | [plan.md](plan.md) | T-013 | [test-spec.md](test-spec.md) |
