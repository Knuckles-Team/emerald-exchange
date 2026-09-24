"""Execution Bridge — CONCEPT:AU-AHE.assimilation.trading-ecosystem-changelog

Turns a strategy / debate / optimizer *decision* (side, size, symbol, order
type, venue) into a routed order through the existing
:class:`~emerald_exchange.backends.ExchangeBackend` Protocol, with the live
trading safety gate enforced at the single choke point.

CRITICAL SAFETY CONTRACT (EH-423)
---------------------------------
The bridge never places a LIVE order. Paper / simulated routing runs freely
(still through :meth:`RiskGuard.pre_trade_check`); a decision on a live
backend returns ``approval_required`` whatever the caller passes. A live order
is placed only by :func:`emerald_exchange.trading.live_orders.execute_approved_order`
for a change set a person approved at the graph-os operator console -- a
boolean argument is not an approval.
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
from emerald_exchange.risk_guards import RiskCheckResult, RiskGuard
from emerald_exchange.trading.governed import LIVE_ORDER_GUIDANCE

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

    1. Paper / simulated backends execute, after ``RiskGuard.pre_trade_check``.
    2. Live backends are never routed: the answer is ``APPROVAL_REQUIRED``
       with the D18 approval path, and no order reaches the backend.
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
            logger.debug("Operation failed: error_type=%s", type(exc).__name__)
        return 100.0

    def route(self, decision: TradeDecision) -> ExecutionDecisionResult:
        """Route one decision: paper executes, live answers approval_required."""
        if not decision.symbol or decision.qty <= 0:
            return self._refused(
                decision, RoutingStatus.REJECTED, "symbol and qty > 0 required"
            )
        if self.is_live:
            logger.warning(
                "LIVE decision for %s not routed — D18 approval required (source=%s)",
                decision.symbol,
                decision.source or "?",
            )
            return self._refused(
                decision, RoutingStatus.APPROVAL_REQUIRED, LIVE_ORDER_GUIDANCE
            )
        acct = self._backend.get_account()
        check = self._risk.pre_trade_check(
            decision.symbol,
            decision.qty,
            self._resolve_price(decision),
            acct.equity,
            acct.cash,
            is_live=False,
        )
        if not check.approved:
            return self._refused(
                decision, RoutingStatus.BLOCKED, check.reason, check.risk_score
            )
        return self._execute(decision, check)

    def _refused(
        self,
        decision: TradeDecision,
        status: RoutingStatus,
        reason: str,
        risk_score: float = 0.0,
    ) -> ExecutionDecisionResult:
        return ExecutionDecisionResult(
            status=status,
            reason=reason,
            decision=decision,
            is_live=self.is_live,
            approved=False,
            risk_score=risk_score,
        )

    def _execute(
        self, decision: TradeDecision, check: RiskCheckResult
    ) -> ExecutionDecisionResult:
        final_qty = check.adjusted_qty if check.adjusted_qty > 0 else decision.qty
        execution = self._backend.submit_order(
            decision.symbol,
            decision.side,
            final_qty,
            decision.order_type,
            decision.limit_price,
        )
        logger.info(
            "Routed paper %s %s %.4f %s via %s",
            decision.side,
            decision.symbol,
            final_qty,
            decision.order_type,
            self._backend.name,
        )
        return ExecutionDecisionResult(
            status=RoutingStatus.EXECUTED,
            reason=check.reason,
            decision=decision,
            is_live=False,
            approved=True,
            risk_score=check.risk_score,
            adjusted_qty=final_qty,
            execution=execution,
        )
