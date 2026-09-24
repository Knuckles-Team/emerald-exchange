"""Live orders only through an approved D18 change set (EH-423).

A real SDK ``DurableWritableConnector`` over the SDK's durable file ledger
stands in for EG's ``WriteBack`` records; the approval lease reader is a dict.
Every refusal path proves the venue was never called.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
from agent_connector_sdk.writeback.durable_ledger import FileWriteBackLedger
from agent_connector_sdk.writeback.errors import WriteBackError
from epistemic_graph.generated.write_back import (
    SourceChangeSet,
    WriteBackAuthorizationDecision,
    WriteBackAuthorizationMode,
)

from emerald_exchange.backends import ExecutionResult, OrderStatus, TradingMode
from emerald_exchange.trading.live_orders import (
    LIVE_ORDER_APPROVAL_KIND,
    ORDER_FIELDS,
    ApprovalRefused,
    VenueRejected,
    change_set_id_for,
    execute_approved_order,
)

TENANT = "tenant-a"
APPROVAL = "finance_order:1"
PROPOSER = "principal:agent"
APPROVER = "principal:operator"
INTENT = {
    "symbol": "AAPL",
    "side": "buy",
    "qty": 2.0,
    "order_type": "limit",
    "limit_price": 101.5,
}


class Venue:
    name = "venue"
    mode = TradingMode.LIVE

    def __init__(self, outcome: str = "filled") -> None:
        self.calls: list[tuple] = []
        self._outcome = outcome

    def submit_order(self, *args: object) -> ExecutionResult:
        self.calls.append(args)
        if self._outcome == "raise":
            raise ConnectionError("socket closed after send")
        status = (
            OrderStatus.REJECTED if self._outcome == "reject" else OrderStatus.FILLED
        )
        return ExecutionResult(f"V-{len(self.calls)}", status, 2, 101.5, 0.1, self.name)


class Leases:
    def __init__(self, **overrides: Any) -> None:
        now = time.time_ns() // 1_000_000
        self.view: dict[str, Any] = {
            "lease_id": APPROVAL,
            "kind": LIVE_ORDER_APPROVAL_KIND,
            "status": "consumed",
            "grant": {"intent": dict(INTENT), "proposer": PROPOSER},
            "issued_at_ms": now,
            "expires_at_ms": now + 300_000,
            "hard_expires_at_ms": now + 300_000,
            "revision": 2,
        }
        self.view.update(overrides)

    async def get(self, *, tenant: str, lease_id: str) -> dict[str, Any] | None:
        return self.view if (tenant, lease_id) == (TENANT, APPROVAL) else None


def change_set(**overrides: Any) -> SourceChangeSet:
    intent = overrides.pop("intent", INTENT)
    authorization = WriteBackAuthorizationDecision(
        mode=overrides.pop("mode", WriteBackAuthorizationMode.PROPOSAL_APPROVAL),
        authorization_ref=APPROVAL,
        decision_digest="2" * 64,
        input_digest="3" * 64,
        output_digest="4" * 64,
        authorized=True,
    )
    fields = {
        "schema_version": 1,
        "change_set_id": change_set_id_for(APPROVAL),
        "change_set_digest": "0" * 64,
        "tenant_id": TENANT,
        "actor": APPROVER,
        "purpose": "live order approved at the operator console",
        "connector_id": "emerald-exchange",
        "source_instance_id": "venue",
        "entity_id": f"order:{APPROVAL}",
        "base_source_version": "absent",
        "desired_patch": dict(intent),
        "field_scope": list(ORDER_FIELDS),
        "source_of_truth_rule": "venue_accepts_order",
        "field_provenance": {name: f"approval:{APPROVAL}" for name in ORDER_FIELDS},
        "required_capability": "finance:order-live",
        "policy_digest": "1" * 64,
        "authorization": authorization,
        "idempotency_key": f"finance-order:{APPROVAL}",
        "expires_at_ms": time.time_ns() // 1_000_000 + 300_000,
        "reconciliation_procedure": "look the order up at the venue",
    }
    fields.update(overrides)
    built = SourceChangeSet(**fields)
    return built.model_copy(update={"change_set_digest": built.canonical_digest()})


def ledger_with(tmp_path: Path, stored: SourceChangeSet | None) -> FileWriteBackLedger:
    ledger = FileWriteBackLedger(tmp_path / "ledger")
    if stored is not None:
        asyncio.run(ledger.create(stored))
    return ledger


def execute(
    ledger: FileWriteBackLedger, venue: Venue, leases: Leases
) -> dict[str, Any]:
    return asyncio.run(
        execute_approved_order(
            APPROVAL, tenant=TENANT, venue=venue, ledger=ledger, leases=leases
        )
    )


def test_an_approved_order_is_placed_exactly_once(tmp_path: Path) -> None:
    ledger, venue = ledger_with(tmp_path, change_set()), Venue()
    first = execute(ledger, venue, Leases())
    again = execute(ledger, venue, Leases())
    assert first["outcome"] == "applied" and first["venue_order"] == "order:V-1"
    assert again == first
    assert len(venue.calls) == 1
    symbol, side, qty, order_type, limit = venue.calls[0]
    assert (symbol, str(side), qty, str(order_type), limit) == (
        "AAPL",
        "buy",
        2.0,
        "limit",
        101.5,
    )


@pytest.mark.parametrize(
    ("leases", "reason"),
    [
        (Leases(status="active"), "not granted"),
        (Leases(status="revoked"), "not granted"),
        (Leases(hard_expires_at_ms=1), "expired"),
        (Leases(kind="action.approval"), "not a live-order approval"),
        (
            Leases(grant={"intent": {**INTENT, "qty": 20.0}, "proposer": PROPOSER}),
            "approved order",
        ),
        (Leases(grant={"intent": dict(INTENT), "proposer": APPROVER}), "own order"),
        (Leases(grant={"intent": dict(INTENT)}), "own order"),
    ],
)
def test_no_granted_matching_approval_means_no_order(
    tmp_path: Path, leases: Leases, reason: str
) -> None:
    ledger, venue = ledger_with(tmp_path, change_set()), Venue()
    with pytest.raises(ApprovalRefused, match=reason):
        execute(ledger, venue, leases)
    assert venue.calls == []


@pytest.mark.parametrize(
    "stored",
    [
        change_set(mode=WriteBackAuthorizationMode.STANDING_POLICY),
        change_set(connector_id="other-connector"),
        change_set(intent={**INTENT, "symbol": "TSLA"}),
    ],
)
def test_a_change_set_that_is_not_the_approved_order_is_refused(
    tmp_path: Path, stored: SourceChangeSet
) -> None:
    ledger, venue = ledger_with(tmp_path, stored), Venue()
    with pytest.raises(ApprovalRefused):
        execute(ledger, venue, Leases())
    assert venue.calls == []


def test_no_durable_change_set_means_no_order(tmp_path: Path) -> None:
    ledger, venue = ledger_with(tmp_path, None), Venue()
    with pytest.raises(ApprovalRefused, match="no approved change set"):
        execute(ledger, venue, Leases())
    assert venue.calls == []


def test_an_uncertain_venue_call_is_never_retried(tmp_path: Path) -> None:
    ledger, venue = ledger_with(tmp_path, change_set()), Venue("raise")
    first = execute(ledger, venue, Leases())
    assert first["outcome"] == "outcome_uncertain"
    with pytest.raises(WriteBackError):
        execute(ledger, venue, Leases())
    assert len(venue.calls) == 1


def test_a_venue_rejection_had_no_effect_and_may_be_retried(tmp_path: Path) -> None:
    ledger, venue = ledger_with(tmp_path, change_set()), Venue("reject")
    with pytest.raises(VenueRejected):
        execute(ledger, venue, Leases())
    with pytest.raises(VenueRejected):
        execute(ledger, venue, Leases())
    assert len(venue.calls) == 2


def test_a_lease_revoked_after_the_first_check_stops_the_venue_call(
    tmp_path: Path,
) -> None:
    ledger, venue = ledger_with(tmp_path, change_set()), Venue()
    leases = Leases()

    class RevokedOnSecondRead(Leases):
        reads = 0

        async def get(self, *, tenant: str, lease_id: str) -> dict[str, Any] | None:
            RevokedOnSecondRead.reads += 1
            view = await leases.get(tenant=tenant, lease_id=lease_id)
            if view is not None and RevokedOnSecondRead.reads > 1:
                return {**view, "status": "revoked"}
            return view

    with pytest.raises(ApprovalRefused, match="not granted"):
        execute(ledger, venue, RevokedOnSecondRead())
    assert venue.calls == []


class _CaptureMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, *args: object, **kwargs: object):
        def _wrap(fn):
            self.tools[fn.__name__] = fn
            return fn

        return _wrap


def test_the_live_tool_fails_closed_without_a_workload_identity(monkeypatch) -> None:
    from emerald_exchange.mcp.mcp_live_orders import register_live_order_tools

    for name in ("EMERALD_EG_PRINCIPAL", "EPISTEMIC_GRAPH_TENANT"):
        monkeypatch.delenv(name, raising=False)
    mcp, venue = _CaptureMCP(), Venue()
    register_live_order_tools(mcp, venue)
    tool = mcp.tools["emerald_live_orders"]
    refused = json.loads(
        asyncio.run(tool(action="execute_approved", approval_id=APPROVAL))
    )
    assert refused == {"status": "refused", "reason": "EMERALD_EG_PRINCIPAL is not set"}
    unknown = json.loads(asyncio.run(tool(action="submit", approval_id=APPROVAL)))
    assert "Unknown action" in unknown["error"]
    assert venue.calls == []
