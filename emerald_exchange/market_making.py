"""Market-Making Controller — CONCEPT:EX-AHE.harness.ee-22.

A per-book-update quoting *policy* implementing the §9 HFT skeleton. It is the
CONTROLLER + venue-decision layer only: it computes intended bid/ask quotes and a
withdraw decision, but it **never places live orders**. Order placement stays in
the backends, gated by ``RiskGuard.require_human_approval_live``.

Math is delegated to the Rust ``epistemic-graph`` engine via the lazy sync client
(``client.finance.*``):

* ``microprice_series`` — size-weighted fair value from the top of book.
* ``ofi_series`` — Cont-Kukanov-Stoikov order-flow imbalance → optional drift.
* ``logit_quotes`` — bounded (0,1) Avellaneda-Stoikov for prediction markets.
* ``avellaneda_stoikov`` — unbounded AS for equities/crypto.
* ``vpin_pm`` + ``breakeven_alpha`` — toxicity gate: widen / withdraw when the
  estimated informed-trader rate exceeds the spread's breakeven alpha.

When the engine is unreachable the controller degrades to a transparent
local-arithmetic fallback (mid ± a configured half-spread) and flags it, so the
caller can choose to withdraw rather than quote blind.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from emerald_exchange._engine import ENGINE_REQUIRED_ERR, finance_engine

logger = logging.getLogger(__name__)


def brier_score(forecasts: list[float], outcomes: list[float]) -> dict[str, Any]:
    """Brier calibration score of probabilistic forecasts vs realized outcomes.

    CONCEPT:EX-AHE.harness.by-default. Tracks how well the quoting/conviction signals are calibrated
    over time (lower = better; 0 = perfect, 0.25 = uninformative coin flip).
    Delegates to the engine ``client.finance.brier_score``; degrades to a clean
    ``{"error": ...}`` when the engine is unreachable or the kernel is missing.

    Args:
        forecasts: probability forecasts in [0, 1].
        outcomes: realized 0/1 outcomes (same length as ``forecasts``).
    """
    if len(forecasts) != len(outcomes):
        return {"error": "forecasts and outcomes must be the same length"}
    if not forecasts:
        return {"error": "forecasts/outcomes are empty"}

    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}
    try:
        score = float(engine.finance.brier_score(forecasts, outcomes))
        return {"brier_score": score, "n": len(forecasts), "engine_used": True}
    except Exception as exc:  # noqa: BLE001 — degrade cleanly (incl. stale daemon)
        logger.debug("brier_score failed: error_type=%s", type(exc).__name__)
        return {"error": "Operation failed"}


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
    queue_fill_time_max: float = 0.0  # >0 withdraws when worst-side fill time exceeds this
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
    """Pure decision policy — computes intended quotes, never places orders.

    CONCEPT:EX-AHE.harness.ee-22.
    """

    def __init__(self, config: MMConfig | None = None) -> None:
        self.config = config or MMConfig()

    # ── helpers ────────────────────────────────────────────────────────
    def _snap(self, px: float) -> float:
        tick = self.config.tick
        if tick <= 0:
            return px
        return round(round(px / tick) * tick, 10)

    def _fair_value(self, book: BookSnapshot, engine: Any) -> tuple[float, bool]:
        """Microprice fair value (engine) with mid fallback."""
        if engine is not None and book.bid_px and book.ask_px:
            try:
                series = engine.finance.microprice_series(
                    book.bid_px, book.bid_sz, book.ask_px, book.ask_sz
                )
                if series:
                    return float(series[-1]), True
            except Exception as exc:  # noqa: BLE001 — degrade to mid
                logger.debug("Operation failed: error_type=%s", type(exc).__name__)
        return book.mid, False

    def _ofi_drift(self, book: BookSnapshot, engine: Any) -> float:
        coef = self.config.ofi_drift_coef
        if coef == 0.0 or engine is None or len(book.ts) < 2:
            return 0.0
        try:
            ofi = engine.finance.ofi_series(
                book.ts,
                book.bid_px,
                book.bid_sz,
                book.ask_px,
                book.ask_sz,
                self.config.ofi_window_secs,
            )
            if ofi:
                return coef * float(ofi[-1])
        except Exception as exc:  # noqa: BLE001
            logger.debug("Operation failed: error_type=%s", type(exc).__name__)
        return 0.0

    def _toxicity(
        self, book: BookSnapshot, half_spread: float, fair_value: float, engine: Any
    ) -> tuple[float, float]:
        """Return (estimated informed-trader alpha, breakeven alpha)."""
        if engine is None or not book.buy_vol or not book.sell_vol:
            return 0.0, 1.0
        try:
            alpha = float(
                engine.finance.vpin_pm(book.buy_vol, book.sell_vol, book.p_mean)
            )
            be = float(
                engine.finance.breakeven_alpha(
                    half_spread, fair_value, self.config.vh, self.config.vl
                )
            )
            return alpha, be
        except Exception as exc:  # noqa: BLE001
            logger.debug("Operation failed: error_type=%s", type(exc).__name__)
            return 0.0, 1.0

    def _surveillance(self, book: BookSnapshot, engine: Any) -> tuple[float, float]:
        """Return ``(legal_risk_score, informed_share)`` from the Kyle surveillance
        kernel (CONCEPT:EX-AHE.harness.sustained-adverse-selection, distils arXiv:2605.27684). Derives signed flow and
        price changes from the book's volume/price buckets. Degrades to
        ``(0.0, 0.0)`` — never blocking blind — when the engine is unreachable or
        the window is too thin. DEFENSIVE: adverse-selection protection only.
        """
        if engine is None or not book.buy_vol or not book.sell_vol:
            return 0.0, 0.0
        try:
            n = min(len(book.buy_vol), len(book.sell_vol))
            signed_flow = [book.buy_vol[i] - book.sell_vol[i] for i in range(n)]
            pm = book.p_mean or []
            price_changes = [pm[i] - pm[i - 1] for i in range(1, len(pm))]
            out = engine.finance.surveillance_risk(
                book.buy_vol,
                book.sell_vol,
                book.p_mean,
                signed_flow,
                price_changes,
                self.config.surveillance_baseline_sigma,
            )
            if isinstance(out, dict):
                return (
                    float(out.get("legal_risk_score", 0.0)),
                    float(out.get("informed_share", 0.0)),
                )
        except Exception as exc:  # noqa: BLE001 — degrade, never block blind
            logger.debug("Operation failed: error_type=%s", type(exc).__name__)
        return 0.0, 0.0

    def _queue_skew(self, book: BookSnapshot, engine: Any) -> tuple[float, float]:
        """Return ``(queue_skew ∈ [-1, 1], worst-side fill_time)``.

        CONCEPT:AU-AHE.assimilation.trading-ecosystem-changelog. ``skew = (ask_q - bid_q)/(ask_q + bid_q)`` — positive ⇒ the
        ask queue is heavier, so a resting bid fills relatively faster. A longer
        ``fill_time`` means more adverse-selection exposure while resting. Uses the
        engine ``queue_imbalance`` kernel with a local-fallback mirror so the
        signal is never silently dropped offline. Falls back to ``bid_sz``/
        ``ask_sz`` for queue lengths when explicit queue sizes aren't supplied.
        """
        bq = book.bid_q or book.bid_sz
        aq = book.ask_q or book.ask_sz
        if not bq or not aq:
            return 0.0, 0.0
        if engine is not None:
            try:
                out = engine.finance.queue_imbalance(
                    bq,
                    aq,
                    book.bid_rate or [1.0] * len(bq),
                    book.ask_rate or [1.0] * len(aq),
                )
                if isinstance(out, dict) and out.get("skew"):
                    fill_time = max(
                        float(out["bid_fill_time"][-1]),
                        float(out["ask_fill_time"][-1]),
                    )
                    return float(out["skew"][-1]), fill_time
            except Exception as exc:  # noqa: BLE001 — degrade to local mirror
                logger.debug("Operation failed: error_type=%s", type(exc).__name__)
        # Local fallback mirroring the kernel: (ask_q - bid_q)/(ask_q + bid_q).
        b, a = float(bq[-1]), float(aq[-1])
        total = a + b
        skew = (a - b) / total if total > 0 else 0.0
        return skew, 0.0

    def _conviction_gate(
        self, signal_strengths: list[float] | None, engine: Any
    ) -> dict[str, Any]:
        """Run the engine convergence gate over the supplied signal strengths.

        CONCEPT:EX-AHE.harness.by-default. Returns the engine's ``convergence_gate`` payload
        ``{agree, total, fraction, direction, pass}``. When no strengths are
        supplied the gate is vacuously *open* (``pass=True``) so the controller
        behaves exactly as before for callers that don't feed signals — but as
        soon as strengths are present, N/N agreement is required to quote.
        Degrades to a local count when the engine is unreachable so the gate is
        never silently bypassed offline.
        """
        cfg = self.config
        if not cfg.conviction_gate or not signal_strengths:
            return {"pass": True, "reason": "gate_off_or_no_signals"}

        if engine is not None:
            try:
                out = engine.finance.convergence_gate(
                    signal_strengths,
                    cfg.conviction_strong_threshold,
                    cfg.conviction_min_agree,
                )
                if isinstance(out, dict):
                    return out
            except Exception as exc:  # noqa: BLE001 — local fallback below
                logger.debug("Operation failed: error_type=%s", type(exc).__name__)

        # Local fallback mirroring the engine's gate semantics.
        thr = cfg.conviction_strong_threshold
        longs = sum(1 for s in signal_strengths if s >= thr)
        shorts = sum(1 for s in signal_strengths if s <= -thr)
        agree = max(longs, shorts)
        direction = 1 if longs >= shorts else -1
        total = len(signal_strengths)
        return {
            "agree": agree,
            "total": total,
            "fraction": (agree / total) if total else 0.0,
            "direction": direction if agree else 0,
            "pass": agree >= cfg.conviction_min_agree,
            "engine_used": False,
        }

    # ── main policy ────────────────────────────────────────────────────
    def decide(
        self,
        book: BookSnapshot,
        inventory: float,
        signal_strengths: list[float] | None = None,
    ) -> QuoteDecision:
        """Compute intended quotes for a single book update (no look-ahead).

        Implements the §9 skeleton: conviction gate → fair value → optional OFI
        drift → AS/logit quotes → VPIN toxicity gate → tick snap → post-only /
        non-crossing.

        The CONVICTION GATE (CONCEPT:EX-AHE.harness.by-default) runs FIRST and is **ON by default**
        (``MMConfig.conviction_gate=True``): when ``signal_strengths`` are
        supplied they must reach ``conviction_min_agree`` strong agreeing votes
        (via the engine ``convergence_gate``) before any quote is emitted —
        otherwise the controller withdraws. With no strengths supplied the gate
        is vacuously open, preserving the prior behavior for unsignalled callers.
        """
        cfg = self.config
        engine = finance_engine()

        # ── Conviction gate FIRST: no agreement ⇒ no quote (decision only). ──
        conviction = self._conviction_gate(signal_strengths, engine)
        if not conviction.get("pass", True):
            return QuoteDecision(
                bid=None,
                ask=None,
                reservation=0.0,
                fair_value=0.0,
                half_spread=0.0,
                withdraw=True,
                reason="conviction_gate_blocked",
                engine_used=engine is not None,
                conviction_pass=False,
                conviction=conviction,
            )

        fair_value, engine_used = self._fair_value(book, engine)
        if fair_value <= 0:
            return QuoteDecision(
                bid=None,
                ask=None,
                reservation=0.0,
                fair_value=0.0,
                half_spread=0.0,
                withdraw=True,
                reason="no_fair_value",
                engine_used=engine_used,
                conviction_pass=True,
                conviction=conviction,
            )

        fair_value += self._ofi_drift(book, engine)
        if cfg.bounded:
            fair_value = min(max(fair_value, 1e-6), 1.0 - 1e-6)

        # AS / logit quotes from the engine, else local symmetric fallback.
        quotes = None
        if engine is not None:
            try:
                if cfg.bounded:
                    quotes = engine.finance.logit_quotes(
                        fair_value,
                        inventory,
                        cfg.sigma,
                        cfg.gamma,
                        cfg.kappa,
                        cfg.tau,
                        cfg.boundary_m,
                    )
                else:
                    quotes = engine.finance.avellaneda_stoikov(
                        fair_value, inventory, cfg.sigma, cfg.gamma, cfg.kappa, cfg.tau
                    )
                engine_used = True
            except Exception as exc:  # noqa: BLE001 — degrade locally
                logger.debug(
                    "AS/logit quotes failed; using local fallback: error_type=%s",
                    type(exc).__name__,
                )
                quotes = None

        if quotes is not None:
            bid = float(quotes.get("bid", fair_value))
            ask = float(quotes.get("ask", fair_value))
            reservation = float(quotes.get("reservation", fair_value))
            half_spread = float(quotes.get("half_spread", abs(ask - bid) / 2.0))
            withdraw = bool(quotes.get("withdraw", False))
            reason = "engine_quotes"
        else:
            # Transparent local fallback: inventory-skewed mid ± vol-scaled half-spread.
            half_spread = max(cfg.tick, cfg.gamma * cfg.sigma)
            reservation = fair_value - inventory * cfg.gamma * (cfg.sigma**2) * cfg.tau
            bid = reservation - half_spread
            ask = reservation + half_spread
            withdraw = False
            reason = "local_fallback"
            engine_used = False

        # VPIN toxicity gate: widen / withdraw when estimated alpha > breakeven.
        tox_alpha, be_alpha = self._toxicity(book, half_spread, fair_value, engine)
        if tox_alpha > 0.0 and be_alpha > 0.0 and tox_alpha > be_alpha:
            # Informed flow exceeds what the spread can survive → pull quotes.
            withdraw = True
            reason = "toxicity_withdraw"

        # Kyle legal-risk / adverse-selection gate (CONCEPT:EX-AHE.harness.sustained-adverse-selection). Always
        # computed + surfaced; withdraws only when the operator threshold trips.
        legal_risk_score, informed_share = self._surveillance(book, engine)
        if legal_risk_score > cfg.legal_risk_max and not withdraw:
            withdraw = True
            reason = "legal_risk_withdraw"

        # Queue-position / adverse-selection (CONCEPT:AU-AHE.assimilation.trading-ecosystem-changelog). Both coefs default
        # to 0 ⇒ no effect, so existing callers are behavior-identical.
        q_skew, fill_time = self._queue_skew(book, engine)
        if cfg.queue_skew_coef != 0.0 and not withdraw:
            # Nudge the reservation (and quotes) toward the thicker queue so we
            # rest where we're less likely to be adversely selected.
            reservation -= cfg.queue_skew_coef * q_skew * half_spread
            bid = reservation - half_spread
            ask = reservation + half_spread
        if cfg.queue_fill_time_max > 0.0 and fill_time > cfg.queue_fill_time_max:
            withdraw = True
            reason = "queue_adverse_selection"

        # Inventory limit: withdraw the side that worsens our position.
        over_long = inventory >= cfg.max_inventory
        over_short = inventory <= -cfg.max_inventory

        # Tick snap.
        bid_s: float | None = self._snap(bid)
        ask_s: float | None = self._snap(ask)

        # Non-crossing / post-only: a bid must not lift the resting ask, and an
        # ask must not hit the resting bid. Otherwise pull that side.
        if cfg.post_only:
            if book.top_ask > 0 and bid_s is not None and bid_s >= book.top_ask:
                bid_s = None
            if book.top_bid > 0 and ask_s is not None and ask_s <= book.top_bid:
                ask_s = None

        if bid_s is not None and ask_s is not None and bid_s >= ask_s:
            # Degenerate locked/crossed quote → withdraw entirely.
            withdraw = True
            reason = reason or "crossed_self"

        if over_long:
            bid_s = None  # stop accumulating more longs
        if over_short:
            ask_s = None  # stop accumulating more shorts

        if cfg.bounded:
            # Keep quotes strictly inside (0, 1).
            if bid_s is not None and bid_s <= 0.0:
                bid_s = None
            if ask_s is not None and ask_s >= 1.0:
                ask_s = None

        if withdraw:
            bid_s = None
            ask_s = None

        if bid_s is None and ask_s is None and not withdraw:
            withdraw = True
            reason = reason or "no_postable_side"

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
            engine_used=engine_used,
            conviction_pass=True,
            conviction=conviction,
            legal_risk_score=legal_risk_score,
            informed_share=informed_share,
        )
