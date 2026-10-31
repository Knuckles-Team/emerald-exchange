"""Market-Making Controller — CONCEPT:EX-AHE.harness.ee-22.

A per-book-update quoting *policy* (the §9 HFT skeleton). Every quantity is an
analysis epistemic-graph runs (``ontology/quant.ttl`` bindings, selected by
SPARQL through :func:`emerald_exchange._engine.run_analysis`):

* ConvictionAnalysis — convergence gate over signal strengths.
* FairValueAnalysis — microprice fair value.
* OrderFlowImbalanceAnalysis — optional OFI drift.
* BoundedQuoteAnalysis / QuoteAnalysis — logit or Avellaneda-Stoikov quotes.
* FlowToxicityAnalysis + BreakevenAlphaAnalysis — toxicity withdraw gate.
* SurveillanceAnalysis — Kyle legal-risk withdraw gate.
* QueuePositionAnalysis — queue skew and fill time.

The connector keeps only venue order rules: tick snap, post-only
non-crossing, inventory caps and the (0, 1) price bounds. There is no local
fallback: an unreachable engine or unserved analysis withdraws both sides.
It never places orders; placement stays in the backends behind
``RiskGuard.require_human_approval_live``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from scion_sdk.compute import ComputeUnavailableError, MethodNotServedError

from emerald_exchange._engine import engine_error, run_analysis

logger = logging.getLogger(__name__)


@dataclass
class BookSnapshot:
    """Top-of-book (and short trailing window) for one symbol/token."""

    ts: list[float] = field(default_factory=list)
    bid_px: list[float] = field(default_factory=list)
    bid_sz: list[float] = field(default_factory=list)
    ask_px: list[float] = field(default_factory=list)
    ask_sz: list[float] = field(default_factory=list)
    # Trailing buy/sell volume + mean price buckets for VPIN toxicity.
    buy_vol: list[float] = field(default_factory=list)
    sell_vol: list[float] = field(default_factory=list)
    p_mean: list[float] = field(default_factory=list)
    # Best-level resting queue sizes + recent arrival rates for the
    # queue-position / time-to-fill signal. When empty, the controller falls
    # back to ``bid_sz``/``ask_sz`` for queue lengths and uniform arrival rates.
    bid_q: list[float] = field(default_factory=list)
    ask_q: list[float] = field(default_factory=list)
    bid_rate: list[float] = field(default_factory=list)
    ask_rate: list[float] = field(default_factory=list)

    @property
    def top_bid(self) -> float:
        return self.bid_px[-1] if self.bid_px else 0.0

    @property
    def top_ask(self) -> float:
        return self.ask_px[-1] if self.ask_px else 0.0

    @property
    def mid(self) -> float:
        b, a = self.top_bid, self.top_ask
        if b > 0 and a > 0:
            return (b + a) / 2.0
        return b or a


@dataclass
class MMConfig:
    """Quoting-policy parameters."""

    gamma: float = 0.1  # inventory risk aversion
    kappa: float = 1.5  # order-arrival intensity decay
    sigma: float = 0.02  # short-horizon volatility estimate
    tau: float = 1.0  # time-to-horizon (normalized)
    tick: float = 0.01  # venue tick size
    bounded: bool = True  # True ⇒ prediction-market (logit_quotes)
    boundary_m: float = 0.0  # logit boundary inventory cap margin
    ofi_drift_coef: float = 0.0  # 0 disables OFI drift; >0 nudges fair value
    ofi_window_secs: float = 1.0
    # Queue-position / adverse-selection (CONCEPT:AU-AHE.assimilation.trading-ecosystem-changelog). Both default to 0 ⇒
    # behavior-identical until an operator opts in (mirrors ofi_drift_coef).
    queue_skew_coef: float = 0.0  # >0 nudges reservation toward the thicker queue
    queue_fill_time_max: float = (
        0.0  # >0 withdraws when worst-side fill time exceeds this
    )
    vh: float = 1.0  # payoff if "high" resolves (YES → 1.0)
    vl: float = 0.0  # payoff if "low" resolves
    post_only: bool = True  # never cross the resting book
    max_inventory: float = 100.0  # |inventory| beyond which we withdraw the loaded side
    # ── Conviction gate (CONCEPT:EX-AHE.harness.by-default) — ON by default ───────────────
    conviction_gate: bool = True  # require N/N strong-signal agreement to quote
    conviction_strong_threshold: float = (
        0.6  # |strength| ≥ this counts as a strong vote
    )
    conviction_min_agree: int = 2  # min agreeing strong votes to pass the gate
    # ── Kyle legal-risk / adverse-selection gate (CONCEPT:EX-AHE.harness.sustained-adverse-selection) ──────
    # The surveillance score is ALWAYS computed and surfaced (native), but the
    # withdraw action requires an operator threshold. Default 1.0 ⇒ never trips
    # (legal_risk_score ∈ [0,1) asymptotes below 1), so behavior is identical
    # until an operator tightens it (e.g. 0.85), mirroring the queue coefs.
    legal_risk_max: float = 1.0  # withdraw when legal_risk_score exceeds this
    surveillance_baseline_sigma: float = 0.0  # 0 ⇒ kernel uses sample std of flow


@dataclass
class QuoteDecision:
    """Intended quotes for one book update — a decision, not an order."""

    bid: float | None
    ask: float | None
    reservation: float
    fair_value: float
    half_spread: float
    withdraw: bool
    toxicity_alpha: float = 0.0
    breakeven_alpha: float = 0.0
    queue_skew: float = 0.0
    queue_fill_time: float = 0.0
    reason: str = ""
    engine_used: bool = False
    # Conviction-gate outcome (CONCEPT:EX-AHE.harness.by-default). When the gate is on and fails,
    # the decision is forced to withdraw (no quotes are posted).
    conviction_pass: bool = True
    conviction: dict[str, Any] = field(default_factory=dict)
    # Kyle surveillance scores (CONCEPT:EX-AHE.harness.sustained-adverse-selection) — always surfaced for
    # observability; legal_risk_score drives the adverse-selection withdraw.
    legal_risk_score: float = 0.0
    informed_share: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "bid": self.bid,
            "ask": self.ask,
            "reservation": self.reservation,
            "fair_value": self.fair_value,
            "half_spread": self.half_spread,
            "withdraw": self.withdraw,
            "toxicity_alpha": self.toxicity_alpha,
            "breakeven_alpha": self.breakeven_alpha,
            "queue_skew": self.queue_skew,
            "queue_fill_time": self.queue_fill_time,
            "reason": self.reason,
            "engine_used": self.engine_used,
            "conviction_pass": self.conviction_pass,
            "conviction": self.conviction,
            "legal_risk_score": self.legal_risk_score,
            "informed_share": self.informed_share,
        }


class MarketMakingController:
    """Quoting policy over epistemic-graph analyses — never places orders.

    CONCEPT:EX-AHE.harness.ee-22.
    """

    def __init__(self, config: MMConfig | None = None) -> None:
        self.config = config or MMConfig()

    def _snap(self, px: float) -> float:
        tick = self.config.tick
        if tick <= 0:
            return px
        return round(round(px / tick) * tick, 10)

    @staticmethod
    def _withdrawn(reason: str, **extra: Any) -> QuoteDecision:
        return QuoteDecision(
            bid=None,
            ask=None,
            reservation=0.0,
            fair_value=0.0,
            half_spread=0.0,
            withdraw=True,
            reason=reason,
            **extra,
        )

    def decide(
        self,
        book: BookSnapshot,
        inventory: float,
        signal_strengths: list[float] | None = None,
    ) -> QuoteDecision:
        """Compute intended quotes for a single book update (no look-ahead)."""
        try:
            return self._decide(book, inventory, signal_strengths)
        except (ComputeUnavailableError, MethodNotServedError) as exc:
            payload = engine_error(exc)
            return self._withdrawn(str(payload["error"]), conviction=payload)

    def _decide(
        self,
        book: BookSnapshot,
        inventory: float,
        signal_strengths: list[float] | None,
    ) -> QuoteDecision:
        cfg = self.config
        conviction: dict[str, Any] = {"pass": True, "reason": "gate_off_or_no_signals"}
        if cfg.conviction_gate and signal_strengths:
            conviction = dict(
                run_analysis(
                    "ConvictionAnalysis",
                    strengths=signal_strengths,
                    strong_threshold=cfg.conviction_strong_threshold,
                    min_agree=cfg.conviction_min_agree,
                )
            )
            if not conviction.get("pass", False):
                return self._withdrawn(
                    "conviction_gate_blocked",
                    engine_used=True,
                    conviction_pass=False,
                    conviction=conviction,
                )
        if not (book.bid_px and book.ask_px):
            return self._withdrawn("no_fair_value", conviction=conviction)
        series = run_analysis(
            "FairValueAnalysis",
            bid_px=book.bid_px,
            bid_sz=book.bid_sz,
            ask_px=book.ask_px,
            ask_sz=book.ask_sz,
        )
        fair_value = float(series[-1]) if series else 0.0
        if fair_value <= 0:
            return self._withdrawn(
                "no_fair_value", engine_used=True, conviction=conviction
            )
        if cfg.ofi_drift_coef != 0.0 and len(book.ts) >= 2:
            ofi = run_analysis(
                "OrderFlowImbalanceAnalysis",
                ts=book.ts,
                bid_px=book.bid_px,
                bid_sz=book.bid_sz,
                ask_px=book.ask_px,
                ask_sz=book.ask_sz,
                window_secs=cfg.ofi_window_secs,
            )
            if ofi:
                fair_value += cfg.ofi_drift_coef * float(ofi[-1])
        if cfg.bounded:
            fair_value = min(max(fair_value, 1e-6), 1.0 - 1e-6)
            quotes = run_analysis(
                "BoundedQuoteAnalysis",
                p_mid=fair_value,
                inventory=inventory,
                sigma=cfg.sigma,
                gamma=cfg.gamma,
                kappa=cfg.kappa,
                tau=cfg.tau,
                boundary_m=cfg.boundary_m,
            )
        else:
            quotes = run_analysis(
                "QuoteAnalysis",
                mid=fair_value,
                inventory=inventory,
                sigma=cfg.sigma,
                gamma=cfg.gamma,
                kappa=cfg.kappa,
                tau=cfg.tau,
            )
        bid = float(quotes["bid"])
        ask = float(quotes["ask"])
        reservation = float(quotes.get("reservation", fair_value))
        half_spread = float(quotes.get("half_spread", abs(ask - bid) / 2.0))
        withdraw = bool(quotes.get("withdraw", False))
        reason = "engine_quotes"

        tox_alpha, be_alpha = 0.0, 0.0
        legal_risk_score, informed_share = 0.0, 0.0
        if book.buy_vol and book.sell_vol:
            tox_alpha = float(
                run_analysis(
                    "FlowToxicityAnalysis",
                    buy_vol=book.buy_vol,
                    sell_vol=book.sell_vol,
                    p_mean=book.p_mean,
                )
            )
            be_alpha = float(
                run_analysis(
                    "BreakevenAlphaAnalysis",
                    delta=half_spread,
                    p=fair_value,
                    v_h=cfg.vh,
                    v_l=cfg.vl,
                )
            )
            if tox_alpha > 0.0 and be_alpha > 0.0 and tox_alpha > be_alpha:
                withdraw, reason = True, "toxicity_withdraw"
            n = min(len(book.buy_vol), len(book.sell_vol))
            pm = book.p_mean or []
            surveillance = run_analysis(
                "SurveillanceAnalysis",
                buy_vol=book.buy_vol,
                sell_vol=book.sell_vol,
                p_mean=book.p_mean,
                signed_flow=[book.buy_vol[i] - book.sell_vol[i] for i in range(n)],
                price_changes=[pm[i] - pm[i - 1] for i in range(1, len(pm))],
                baseline_sigma=cfg.surveillance_baseline_sigma,
            )
            legal_risk_score = float(surveillance.get("legal_risk_score", 0.0))
            informed_share = float(surveillance.get("informed_share", 0.0))
            if legal_risk_score > cfg.legal_risk_max and not withdraw:
                withdraw, reason = True, "legal_risk_withdraw"

        q_skew, fill_time = 0.0, 0.0
        bq = book.bid_q or book.bid_sz
        aq = book.ask_q or book.ask_sz
        if bq and aq:
            queue = run_analysis(
                "QueuePositionAnalysis",
                bid_q=bq,
                ask_q=aq,
                bid_rate=book.bid_rate or [1.0] * len(bq),
                ask_rate=book.ask_rate or [1.0] * len(aq),
            )
            if queue.get("skew"):
                q_skew = float(queue["skew"][-1])
                fill_time = max(
                    float(queue["bid_fill_time"][-1]), float(queue["ask_fill_time"][-1])
                )
        if cfg.queue_skew_coef != 0.0 and not withdraw:
            reservation -= cfg.queue_skew_coef * q_skew * half_spread
            bid = reservation - half_spread
            ask = reservation + half_spread
        if cfg.queue_fill_time_max > 0.0 and fill_time > cfg.queue_fill_time_max:
            withdraw, reason = True, "queue_adverse_selection"

        bid_s, ask_s = self._venue_sides(book, bid, ask, inventory)
        if bid_s is not None and ask_s is not None and bid_s >= ask_s:
            withdraw = True
        if withdraw:
            bid_s = ask_s = None
        elif bid_s is None and ask_s is None:
            withdraw, reason = True, "no_postable_side"
        return QuoteDecision(
            bid=bid_s,
            ask=ask_s,
            reservation=reservation,
            fair_value=fair_value,
            half_spread=half_spread,
            withdraw=withdraw,
            toxicity_alpha=tox_alpha,
            breakeven_alpha=be_alpha,
            queue_skew=q_skew,
            queue_fill_time=fill_time,
            reason=reason,
            engine_used=True,
            conviction_pass=True,
            conviction=conviction,
            legal_risk_score=legal_risk_score,
            informed_share=informed_share,
        )

    def _venue_sides(
        self, book: BookSnapshot, bid: float, ask: float, inventory: float
    ) -> tuple[float | None, float | None]:
        """Venue order rules: tick snap, post-only, inventory caps, (0, 1) bounds."""
        cfg = self.config
        bid_s: float | None = self._snap(bid)
        ask_s: float | None = self._snap(ask)
        if cfg.post_only:
            if book.top_ask > 0 and bid_s is not None and bid_s >= book.top_ask:
                bid_s = None
            if book.top_bid > 0 and ask_s is not None and ask_s <= book.top_bid:
                ask_s = None
        if inventory >= cfg.max_inventory:
            bid_s = None
        if inventory <= -cfg.max_inventory:
            ask_s = None
        if cfg.bounded:
            if bid_s is not None and bid_s <= 0.0:
                bid_s = None
            if ask_s is not None and ask_s >= 1.0:
                ask_s = None
        return bid_s, ask_s
