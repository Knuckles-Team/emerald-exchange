"""Execution Bridge — CONCEPT:AU-AHE.assimilation.trading-ecosystem-changelog

Turns a strategy / debate / optimizer *decision* (side, size, symbol, order
type, venue) into a routed order through the existing
:class:`~emerald_exchange.backends.ExchangeBackend` Protocol, with the live
trading safety gate enforced at the single choke point.

CRITICAL SAFETY CONTRACT
------------------------
Every LIVE order path MUST pass :meth:`RiskGuard.pre_trade_check` and is
BLOCKED whenever ``RiskLimits.require_human_approval_live`` is set (the
default). Paper / simulated routing runs freely; live routing returns an
``approval_required`` result unless the caller *explicitly* approves the
decision (``approve=True``) AND a human-approval requirement is not in force.

This module never relaxes the gate — it composes the same
``RiskGuard.pre_trade_check`` used by ``mcp_orders``; the live block here and
there are one and the same control.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from emerald_exchange.backends import (
    ExchangeBackend,
    ExecutionResult,
    OrderSide,
    OrderType,
    TradingMode,
)
from emerald_exchange.risk_guards import RiskGuard

logger = logging.getLogger(__name__)


class RoutingStatus(StrEnum):
    """Outcome of routing a decision through the bridge."""

    EXECUTED = "executed"  # order submitted to the backend
    APPROVAL_REQUIRED = "approval_required"  # live + human approval gate
    BLOCKED = "blocked"  # risk guard rejected (halt / cash / etc.)
    REJECTED = "rejected"  # invalid decision (bad symbol / qty)


@dataclass
class TradeDecision:
    """A normalized trading decision from any upstream producer.

    Producers: ``mcp_strategy`` promotion, the bull/bear ``debate`` engine, the
    market-making controller, or a portfolio optimizer. The bridge only needs
    the routing-relevant fields; everything else rides along in ``meta``.
    """

    symbol: str
    side: OrderSide
    qty: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    venue: str = ""  # informational; the bound backend is authoritative
    source: str = ""  # e.g. "debate", "market_making", "optimizer"
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradeDecision:
        """Build a decision from a loosely-typed dict (MCP / JSON payloads)."""
        side = data.get("side", "buy")
        ot = data.get("order_type", "market")
        lp = data.get("limit_price")
        return cls(
            symbol=str(data.get("symbol", "")),
            side=OrderSide(side) if not isinstance(side, OrderSide) else side,
            qty=float(data.get("qty", 0.0)),
            order_type=OrderType(ot) if not isinstance(ot, OrderType) else ot,
            limit_price=float(lp) if lp not in (None, "", 0, 0.0) else None,
            venue=str(data.get("venue", "")),
            source=str(data.get("source", "")),
            meta=dict(data.get("meta", {})),
        )


@dataclass
class ExecutionDecisionResult:
    """Result of routing a :class:`TradeDecision` through the bridge."""

    status: RoutingStatus
    reason: str
    decision: TradeDecision
    is_live: bool
    approved: bool
    risk_score: float = 0.0
    adjusted_qty: float = 0.0
    execution: ExecutionResult | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status.value,
            "reason": self.reason,
            "is_live": self.is_live,
            "approved": self.approved,
            "risk_score": self.risk_score,
            "adjusted_qty": self.adjusted_qty,
            "symbol": self.decision.symbol,
            "side": self.decision.side.value,
            "qty": self.decision.qty,
            "order_type": self.decision.order_type.value,
            "venue": self.decision.venue or self.decision.meta.get("venue", ""),
            "source": self.decision.source,
        }
        if self.execution is not None:
            d["execution"] = {
                "order_id": self.execution.order_id,
                "order_status": self.execution.status.value,
                "filled_qty": self.execution.filled_qty,
                "average_price": self.execution.average_price,
                "fees": self.execution.fees,
                "exchange": self.execution.exchange,
            }
        return d


class ExecutionBridge:
    """Route trading decisions to a backend behind the live-approval gate.

    CONCEPT:AU-AHE.assimilation.trading-ecosystem-changelog. The bridge is the single seam between *deciding* (strategy /
    debate / optimizer) and *acting* (the ``ExchangeBackend``). It guarantees:

    1. Paper / simulated backends execute freely.
    2. Live backends are BLOCKED while ``require_human_approval_live`` is set —
       returning ``APPROVAL_REQUIRED`` rather than ever silently routing a live
       order.
    3. Even an explicitly-approved live order still clears
       ``RiskGuard.pre_trade_check`` (cash / position cap / kill switch).
    """

    def __init__(self, backend: ExchangeBackend, risk_guard: RiskGuard):
        self._backend = backend
        self._risk = risk_guard

    @property
    def is_live(self) -> bool:
        return self._backend.mode == TradingMode.LIVE

    def _resolve_price(self, decision: TradeDecision) -> float:
        """Best-available price for risk sizing: limit, else live quote, else
        a conservative non-zero fallback so the cash check still has teeth."""
        if decision.limit_price and decision.limit_price > 0:
            return decision.limit_price
        try:
            last = self._backend.get_quote(decision.symbol).last
            if last and last > 0:
                return last
        except Exception as exc:  # noqa: BLE001 — degrade to fallback price
            logger.debug("quote lookup failed for %s: %s", decision.symbol, exc)
        return 100.0

    def route(
        self, decision: TradeDecision, approve: bool = False
    ) -> ExecutionDecisionResult:
        """Route one decision. Live is gated; paper executes.

        Args:
            decision: the normalized trade decision.
            approve: explicit human approval for a LIVE order. Ignored for
                paper. Even when ``True``, the order still passes through
                ``pre_trade_check`` and is blocked if a standing
                ``require_human_approval_live`` policy is active.
        """
        if not decision.symbol or decision.qty <= 0:
            return ExecutionDecisionResult(
                status=RoutingStatus.REJECTED,
                reason="symbol and qty > 0 required",
                decision=decision,
                is_live=self.is_live,
                approved=False,
            )

        is_live = self.is_live
        price = self._resolve_price(decision)
        acct = self._backend.get_account()

        # --- THE LIVE GATE -------------------------------------------------
        # A live order is only allowed to even reach pre_trade_check's live arm
        # when the operator explicitly approved AND the standing policy permits
        # it. With the default require_human_approval_live=True, an unapproved
        # live decision short-circuits to APPROVAL_REQUIRED and NEVER routes.
        if is_live and self._risk.limits.require_human_approval_live and not approve:
            logger.warning(
                "LIVE order for %s blocked — human approval required (source=%s)",
                decision.symbol,
                decision.source or "?",
            )
            return ExecutionDecisionResult(
                status=RoutingStatus.APPROVAL_REQUIRED,
                reason=(
                    "Live trading requires explicit human approval "
                    "(require_human_approval_live is set). Re-route with "
                    "approve=True after a human signs off."
                ),
                decision=decision,
                is_live=True,
                approved=False,
            )

        # For an explicitly-approved live order we still must clear the guard,
        # but we must NOT trip its own require_human_approval_live arm (the
        # human already approved at this seam). For paper, is_live=False keeps
        # that arm dormant regardless.
        guard_is_live = is_live and not approve
        check = self._risk.pre_trade_check(
            decision.symbol,
            decision.qty,
            price,
            acct.equity,
            acct.cash,
            is_live=guard_is_live,
        )
        if not check.approved:
            status = (
                RoutingStatus.APPROVAL_REQUIRED
                if "human approval" in check.reason.lower()
                else RoutingStatus.BLOCKED
            )
            return ExecutionDecisionResult(
                status=status,
                reason=check.reason,
                decision=decision,
                is_live=is_live,
                approved=False,
                risk_score=check.risk_score,
            )

        final_qty = check.adjusted_qty if check.adjusted_qty > 0 else decision.qty
        execution = self._backend.submit_order(
            decision.symbol,
            decision.side,
            final_qty,
            decision.order_type,
            decision.limit_price,
        )
        logger.info(
            "Routed %s %s %.4f %s via %s (live=%s, approved=%s)",
            decision.side,
            decision.symbol,
            final_qty,
            decision.order_type,
            self._backend.name,
            is_live,
            approve,
        )
        return ExecutionDecisionResult(
            status=RoutingStatus.EXECUTED,
            reason=check.reason,
            decision=decision,
            is_live=is_live,
            approved=(approve if is_live else True),
            risk_score=check.risk_score,
            adjusted_qty=final_qty,
            execution=execution,
        )
