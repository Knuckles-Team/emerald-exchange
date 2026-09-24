"""Live orders: one human-approved D18 change set, applied once (EH-423).

A live order has exactly one path to a venue:

1. graph-os ``graph_finance(action="propose_order")`` issues a ``finance.order.approval``
   ``ControlLease`` (``active`` = pending) whose grant holds the order
   ``intent`` and the ``proposer`` principal.
2. A person approves it at the graph-os operator console
   (``POST /finance/orders/approve``, a plain route no agent tool reaches).
   The route moves the lease to ``consumed`` and creates the EG ``WriteBack``
   change set ``finance-order:<approval id>`` under the approver's verified
   session -- EG refuses a change set whose ``actor`` is not the verified
   caller, so the record names who authorised the effect.
3. :func:`execute_approved_order` reads that durable change set, checks it
   against the lease (:func:`require_approved`), and applies it through the
   SDK's :class:`~agent_connector_sdk.writeback.connector.DurableWritableConnector`,
   which appends the attempt receipt before returning. The lease is checked
   again immediately before the venue call.

Re-running an applied change set returns the recorded attempt: the effect
happens once. A venue call that fails after it may have reached the venue is
``outcome_uncertain``; reconciliation cannot prove a no-effect without venue
client-order ids, so it stays uncertain and a person resolves it at the venue
-- the order is never retried automatically.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

from agent_connector_sdk.ports.writeback_ledger import WriteBackLedger
from agent_connector_sdk.writeback.connector import DurableWritableConnector
from agent_connector_sdk.writeback.errors import OutcomeUncertainError, WriteBackError
from agent_connector_sdk.writeback.models import DryRunObservation, SourceSnapshot
from epistemic_graph.generated.write_back import (
    ReconciliationObservation,
    SourceChangeSet,
    WriteBackAttempt,
    WriteBackAttemptKind,
    WriteBackAuthorizationMode,
    WriteBackEffectStatus,
    WriteBackOutcome,
    WriteBackReceipt,
)

from emerald_exchange.backends import (
    ExchangeBackend,
    ExecutionResult,
    OrderSide,
    OrderStatus,
    OrderType,
)

__all__ = [
    "ABSENT_VERSION",
    "CONNECTOR_ID",
    "LIVE_ORDER_APPROVAL_KIND",
    "ORDER_FIELDS",
    "ApprovalLeaseReader",
    "ApprovalRefused",
    "LiveOrderTransport",
    "VenueRejected",
    "change_set_id_for",
    "execute_approved_order",
    "require_approved",
]

#: The ControlLease kind of a pending/decided live-order approval.
LIVE_ORDER_APPROVAL_KIND = "finance.order.approval"
#: The D18 connector id every live-order change set names.
CONNECTOR_ID = "emerald-exchange"
#: The order fields a change set patches, in the order the venue takes them.
ORDER_FIELDS = ("symbol", "side", "qty", "order_type", "limit_price")
#: The source version of an order that has not been placed.
ABSENT_VERSION = "absent"
_RECEIPT_PAGE = 256


class ApprovalRefused(PermissionError):
    """The change set is not backed by a granted, matching approval."""


class VenueRejected(WriteBackError):
    """The venue refused the order; no effect happened, a retry is allowed."""


class ApprovalLeaseReader(Protocol):
    """The EG ``control_leases`` read this module needs."""

    async def get(self, *, tenant: str, lease_id: str) -> dict[str, Any] | None:
        """The caller tenant's view of one lease, or ``None``."""
        ...


def change_set_id_for(approval_id: str) -> str:
    """The one change-set id an approval authorises."""
    return f"finance-order:{approval_id}"


def _grant(lease: Mapping[str, Any]) -> Mapping[str, Any]:
    grant = lease.get("grant")
    return grant if isinstance(grant, Mapping) else {}


def _approved_intent(lease: Mapping[str, Any]) -> Mapping[str, Any]:
    intent = _grant(lease).get("intent")
    return intent if isinstance(intent, Mapping) else {}


def _patch_is_intent(lease: Mapping[str, Any], change_set: SourceChangeSet) -> bool:
    patch = {name: change_set.desired_patch.get(name) for name in ORDER_FIELDS}
    return set(change_set.desired_patch) == set(ORDER_FIELDS) and patch == dict(
        _approved_intent(lease)
    )


def _binds_this_approval(lease: Mapping[str, Any], change_set: SourceChangeSet) -> bool:
    approval_id = str(lease.get("lease_id", ""))
    return (
        change_set.change_set_id == change_set_id_for(approval_id)
        and change_set.authorization.authorization_ref == approval_id
    )


_Check = Callable[[Mapping[str, Any], SourceChangeSet, int], bool]

#: Every condition a change set must meet against its approval lease, with
#: the refusal each failure reports. Read top to bottom; all must hold.
_APPROVAL_CHECKS: tuple[tuple[str, _Check], ...] = (
    (
        "not a live-order approval",
        lambda lease, _cs, _now: lease.get("kind") == LIVE_ORDER_APPROVAL_KIND,
    ),
    (
        "the approval is not granted",
        lambda lease, _cs, _now: lease.get("status") == "consumed",
    ),
    (
        "the approval has expired",
        lambda lease, _cs, now: now < int(lease.get("hard_expires_at_ms", 0)),
    ),
    (
        "the change set is not this approval's",
        lambda lease, cs, _now: _binds_this_approval(lease, cs),
    ),
    (
        "the change set targets another connector",
        lambda _lease, cs, _now: cs.connector_id == CONNECTOR_ID,
    ),
    (
        "the change set is not a proposal approval",
        lambda _lease, cs, _now: (
            cs.authorization.mode is WriteBackAuthorizationMode.PROPOSAL_APPROVAL
            and cs.authorization.authorized
        ),
    ),
    (
        "the change set does not carry the approved order",
        lambda lease, cs, _now: _patch_is_intent(lease, cs),
    ),
    (
        "the proposer cannot authorise its own order",
        lambda lease, cs, _now: (
            bool(_grant(lease).get("proposer"))
            and cs.actor != _grant(lease).get("proposer")
        ),
    ),
)


def require_approved(
    lease: Mapping[str, Any] | None, change_set: SourceChangeSet, now_ms: int
) -> None:
    """Refuse unless ``lease`` is a granted approval of exactly ``change_set``."""
    if lease is None:
        raise ApprovalRefused("the approval lease is missing")
    for reason, holds in _APPROVAL_CHECKS:
        if not holds(lease, change_set, now_ms):
            raise ApprovalRefused(reason)


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _order_args(
    patch: Mapping[str, Any],
) -> tuple[str, OrderSide, float, OrderType, float | None]:
    limit = patch.get("limit_price")
    return (
        str(patch["symbol"]),
        OrderSide(str(patch["side"])),
        float(patch["qty"]),
        OrderType(str(patch["order_type"])),
        float(limit) if limit is not None else None,
    )


def _attempt(
    change_set: SourceChangeSet,
    *,
    pre_version: str,
    post_version: str,
    observation: object,
) -> WriteBackAttempt:
    authorization = change_set.authorization
    return WriteBackAttempt(
        tenant_id=change_set.tenant_id,
        change_set_id=change_set.change_set_id,
        change_set_digest=change_set.change_set_digest,
        idempotency_key=change_set.idempotency_key,
        kind=WriteBackAttemptKind.APPLY,
        input_digest=authorization.input_digest,
        output_digest=authorization.output_digest,
        pre_source_version=pre_version,
        post_source_version=post_version,
        applied_field_digest=change_set.patch_digest(),
        outcome=WriteBackOutcome.APPLIED,
        effect_status=WriteBackEffectStatus.APPLIED,
        connector_observation_digest=_digest(observation),
        provenance_digest=_digest(change_set.field_provenance),
    )


def _attempt_from_receipt(receipt: WriteBackReceipt) -> WriteBackAttempt:
    fields = {name: getattr(receipt, name) for name in WriteBackAttempt.model_fields}
    return WriteBackAttempt(**fields)


def _applied(receipt: object) -> WriteBackReceipt | None:
    body = getattr(receipt, "receipt", None)
    if not isinstance(body, WriteBackReceipt):
        return None
    return body if body.outcome is WriteBackOutcome.APPLIED else None


class LiveOrderTransport:
    """The D18 source transport for one venue: a placed order is the effect."""

    def __init__(
        self,
        venue: ExchangeBackend,
        ledger: WriteBackLedger,
        gate: Callable[[SourceChangeSet], Awaitable[None]],
    ) -> None:
        self._venue = venue
        self._ledger = ledger
        self._gate = gate

    async def read_current(self, change_set: SourceChangeSet) -> SourceSnapshot:
        """An unplaced order is ``absent``; a placed one is its venue order id."""
        prior = await self.prior_effect(change_set)
        if prior is None:
            return SourceSnapshot(source_version=ABSENT_VERSION, fields={})
        return SourceSnapshot(
            source_version=prior.post_source_version,
            fields=dict(change_set.desired_patch),
        )

    async def preview(
        self, change_set: SourceChangeSet, current: SourceSnapshot
    ) -> DryRunObservation:
        """The order the change set would place, without placing it."""
        before = {name: current.fields.get(name) for name in change_set.field_scope}
        after = {
            name: change_set.desired_patch.get(name) for name in change_set.field_scope
        }
        changed = tuple(
            name for name in change_set.field_scope if before[name] != after[name]
        )
        return DryRunObservation(
            change_set_digest=change_set.change_set_digest,
            source_version=current.source_version,
            desired_patch_digest=change_set.patch_digest(),
            changed_fields=changed,
            before=before,
            after=after,
        )

    async def prior_effect(
        self, change_set: SourceChangeSet
    ) -> WriteBackAttempt | None:
        """The applied attempt EG already holds for this change set, if any."""
        after: int | None = None
        while True:
            page = await self._ledger.receipts(
                change_set.tenant_id,
                change_set.change_set_id,
                after_sequence=after,
                limit=_RECEIPT_PAGE,
            )
            for record in page.receipts:
                applied = _applied(record)
                if applied is not None:
                    return _attempt_from_receipt(applied)
            if page.next_sequence is None:
                return None
            after = page.next_sequence

    async def apply(
        self, change_set: SourceChangeSet, expected_version: str
    ) -> WriteBackAttempt:
        """Re-check the approval, then place the order exactly once."""
        await self._gate(change_set)
        try:
            result: ExecutionResult = await asyncio.to_thread(
                self._venue.submit_order, *_order_args(change_set.desired_patch)
            )
        except Exception as exc:
            raise OutcomeUncertainError(
                "the venue call failed after it may have placed the order"
            ) from exc
        if result.status == OrderStatus.REJECTED:
            raise VenueRejected(f"the venue rejected the order: {result.raw}")
        return _attempt(
            change_set,
            pre_version=expected_version,
            post_version=f"order:{result.order_id}",
            observation={
                "order_id": result.order_id,
                "status": str(result.status),
                "exchange": result.exchange,
            },
        )

    async def reconcile(self, change_set: SourceChangeSet) -> ReconciliationObservation:
        """Without venue client-order ids no-effect is unprovable: stay uncertain."""
        observation = {"change_set_id": change_set.change_set_id, "resolved": False}
        return ReconciliationObservation(
            tenant_id=change_set.tenant_id,
            change_set_id=change_set.change_set_id,
            change_set_digest=change_set.change_set_digest,
            idempotency_key=change_set.idempotency_key,
            observed_source_version=ABSENT_VERSION,
            effect_status=WriteBackEffectStatus.OUTCOME_UNCERTAIN,
            retry_allowed=False,
            evidence_digest=_digest(observation),
            connector_observation_digest=_digest(observation),
            provenance_digest=_digest(change_set.field_provenance),
        )


def _lease_gate(
    leases: ApprovalLeaseReader, tenant: str, clock_ms: Callable[[], int]
) -> Callable[[SourceChangeSet], Awaitable[None]]:
    async def gate(change_set: SourceChangeSet) -> None:
        approval_id = change_set.authorization.authorization_ref
        lease = await leases.get(tenant=tenant, lease_id=approval_id)
        require_approved(lease, change_set, clock_ms())

    return gate


async def execute_approved_order(
    approval_id: str,
    *,
    tenant: str,
    venue: ExchangeBackend,
    ledger: WriteBackLedger,
    leases: ApprovalLeaseReader,
    clock_ms: Callable[[], int] = _now_ms,
) -> dict[str, Any]:
    """Place the order one approval authorised, once, and report the receipt."""
    change_set = await ledger.get(tenant, change_set_id_for(approval_id))
    if change_set is None:
        raise ApprovalRefused("no approved change set exists for this approval")
    gate = _lease_gate(leases, tenant, clock_ms)
    await gate(change_set)
    transport = LiveOrderTransport(venue, ledger, gate)
    attempt = await DurableWritableConnector(CONNECTOR_ID, transport, ledger).apply(
        change_set
    )
    return {
        "approval_id": approval_id,
        "change_set_id": change_set.change_set_id,
        "outcome": attempt.outcome.value,
        "effect_status": attempt.effect_status.value,
        "venue_order": attempt.post_source_version,
    }
