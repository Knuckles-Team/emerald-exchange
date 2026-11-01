# EMERALD-OPS — Exchange read operations

**Owner:** Emerald Exchange. **Delivery:** SPECIFIED. **Acceptance:** NOT_AUDITED.

See [`requirements.md`](requirements.md) for the definition of every requirement ID this spec owns and [`status.json`](status.json) for their current delivery and acceptance state.

## Outcome

The exchange backend's read-only operations are served as one typed MCP tool each: `emerald_exchange_get_quote`, `_get_historical`, `_get_positions`, `_get_account`, `_get_order_status` and `_exchanges`. The `exchanges` operation lists the available exchange backends, the active backend and its mode, so a caller can see what the server is connected to before reading data.

## Requirements

| ID | Requirement | Evidence |
| --- | --- | --- |
| OPS-1 | Every read-only backend operation, including `exchanges`, is a per-operation tool | `tests/test_order_guard.py` |
| OPS-2 | Writes (submit, cancel, connect, disconnect) are never per-operation tools; orders go through the risk-guarded `emerald_orders_*` tools | `tests/test_order_guard.py` |

## Boundaries

State-changing operations stay behind RiskGuard limits, halts and live-mode approval (`mcp/mcp_orders.py`). `exchanges` reports configuration only and changes nothing.

## Why a new spec

The specs of this repository were read; none owns this capability. This spec states it for this connector only.

## Scope and interfaces

In scope: the rows of [requirements.md](requirements.md). Out of scope: the SDK modules and the engine, which own the shared capabilities.

## User Scenarios & Testing

### User Story 1 - Exchange read operations (Priority: P1)

The exchange backend's read-only operations are served as one typed MCP tool each: `emerald_exchange_get_quote`, `_get_historical`, `_get_positions`, `_get_account`, `_get_order_status` and `_exchanges`. The `exchanges` operation lists the available exchange backends, the active backend and its mode, so a caller can see what the server is connected to before reading data.

**Acceptance Scenarios**:

1. **Given** the connector is configured, **When** the behaviour of row `EMERALD-OPS-R001` (read-only exchange operations are per-operation tools) is exercised, **Then** read-only exchange operations are per-operation tools.
2. **Given** the connector is configured, **When** the behaviour of row `EMERALD-OPS-R002` (fleet name) is exercised, **Then** every connector name in the package is `emerald-exchange-mcp`.
3. **Given** the connector is configured, **When** the behaviour of row `EMERALD-OPS-R003` (alpaca account reads retain provider identity and fail closed) is exercised, **Then** `tests/test_alpaca_account_integrity.py` covers the provider adapter, real in-process MCP tool, invalid responses and redacted transport failures. Test: `tests/test_alpaca_account_integrity.py::test_real_served_account_tool_exposes_provider_identity`.

### Edge Cases

- If `EMERALD-OPS-R001` is not met, its proving test fails: read-only exchange operations are per-operation tools.
- If `EMERALD-OPS-R002` is not met, its proving test fails: fleet name.
- If `EMERALD-OPS-R003` is not met, its proving test fails: alpaca account reads retain provider identity and fail closed.

## Requirements

- **FR-001**: Read-only exchange operations are per-operation tools. Rows: `EMERALD-OPS-R001`.
- **FR-002**: Fleet name. Rows: `EMERALD-OPS-R002`.
- **FR-003**: Alpaca account reads retain provider identity and fail closed. Rows: `EMERALD-OPS-R003`.
- **FR-004**: Declare an Alpaca account snapshot source. Rows: `EMERALD-OPS-R004`.
- **FR-005**: Prediction-market and order read tools for arbora. Rows: `EMERALD-OPS-R005`.
- **FR-006**: Order routing requires the arbora confirmation receipt. Rows: `EMERALD-OPS-R006`.
- **FR-007**: Quant analysis bindings use numeric.evaluate. Rows: `EMERALD-OPS-R007`.
- **FR-008**: Order routing requires an admission receipt. Rows: `EMERALD-OPS-R008`.
- **FR-009**: Pattern and attribution actions call the engine. Rows: `EMERALD-OPS-R009`.
- **FR-010**: Research record tools. Rows: `EMERALD-OPS-R010`.
- **FR-011**: Position sizing tool calls the engine. Rows: `EMERALD-OPS-R011`.
- **FR-012**: Distribution-shift analysis calls the engine. Rows: `EMERALD-OPS-R012`.
- **FR-013**: Banking kernels tool calls the engine. Rows: `EMERALD-OPS-R013`.
- **FR-014**: Served wallet operation tool composes the SDK proof gate. Rows: `EMERALD-OPS-R014`.

## Success Criteria

- **SC-001**: Read-only exchange operations are per-operation tools. Rows: `EMERALD-OPS-R001`.
- **SC-002**: Every connector name in the package is `emerald-exchange-mcp`. Rows: `EMERALD-OPS-R002`.
- **SC-003**: `tests/test_alpaca_account_integrity.py` covers the provider adapter, real in-process MCP tool, invalid responses and redacted transport failures. Rows: `EMERALD-OPS-R003`.
- **SC-004**: `tests/test_alpaca_account_integrity.py::test_snapshot_source_is_declared_and_served` and `test_snapshot_source_refuses_incomplete_account_or_position_reads`. Rows: `EMERALD-OPS-R004`.
- **SC-005**: Prediction-market and order read tools for arbora. Rows: `EMERALD-OPS-R005`.
- **SC-006**: Order routing requires the arbora confirmation receipt. Rows: `EMERALD-OPS-R006`.
- **SC-007**: `tests/test_quant_bindings.py::test_every_kernel_binding_uses_numeric_evaluate` (L3) reads `quant.ttl` and calls `emerald_statarb` against a recorded engine response. Rows: `EMERALD-OPS-R007`.
- **SC-008**: `tests/test_order_admission.py::test_order_refused_without_receipt` (L3) against a recorded venue response. Rows: `EMERALD-OPS-R008`.
- **SC-009**: Pattern and attribution actions call the engine. Rows: `EMERALD-OPS-R009`.
- **SC-010**: Research record tools. Rows: `EMERALD-OPS-R010`.
- **SC-011**: Position sizing tool calls the engine. Rows: `EMERALD-OPS-R011`.
- **SC-012**: Distribution-shift analysis calls the engine. Rows: `EMERALD-OPS-R012`.
- **SC-013**: Banking kernels tool calls the engine. Rows: `EMERALD-OPS-R013`.
- **SC-014**: Served wallet operation tool composes the SDK proof gate. Rows: `EMERALD-OPS-R014`.

## Assumptions

- The external system is reachable with operator-supplied credentials.
- The SDK and engine contracts the rows cite are at the floors declared in `pyproject.toml`.

## Traceability

| Label | Rows | Design section | Test ID | Evidence |
|---|---|---|---|---|
| FR-001 | `EMERALD-OPS-R001` | [plan.md](plan.md) | T-001 | [test-spec.md](test-spec.md) |
| FR-002 | `EMERALD-OPS-R002` | [plan.md](plan.md) | T-002 | [test-spec.md](test-spec.md) |
| FR-003 | `EMERALD-OPS-R003` | [plan.md](plan.md) | T-003 | [test-spec.md](test-spec.md) |
| FR-004 | `EMERALD-OPS-R004` | [plan.md](plan.md) | T-004 | [test-spec.md](test-spec.md) |
| FR-005 | `EMERALD-OPS-R005` | [plan.md](plan.md) | T-005 | [test-spec.md](test-spec.md) |
| FR-006 | `EMERALD-OPS-R006` | [plan.md](plan.md) | T-006 | [test-spec.md](test-spec.md) |
| FR-007 | `EMERALD-OPS-R007` | [plan.md](plan.md) | T-007 | [test-spec.md](test-spec.md) |
| FR-008 | `EMERALD-OPS-R008` | [plan.md](plan.md) | T-008 | [test-spec.md](test-spec.md) |
| FR-009 | `EMERALD-OPS-R009` | [plan.md](plan.md) | T-009 | [test-spec.md](test-spec.md) |
| FR-010 | `EMERALD-OPS-R010` | [plan.md](plan.md) | T-010 | [test-spec.md](test-spec.md) |
| FR-011 | `EMERALD-OPS-R011` | [plan.md](plan.md) | T-011 | [test-spec.md](test-spec.md) |
| FR-012 | `EMERALD-OPS-R012` | [plan.md](plan.md) | T-012 | [test-spec.md](test-spec.md) |
| FR-013 | `EMERALD-OPS-R013` | [plan.md](plan.md) | T-013 | [test-spec.md](test-spec.md) |
| FR-014 | `EMERALD-OPS-R014` | [plan.md](plan.md) | T-014 | [test-spec.md](test-spec.md) |
