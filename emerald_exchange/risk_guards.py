"""Risk Guards — CONCEPT:EE-007 / OS-5.1

Pre-trade risk validation, circuit breakers, and kill switch.
All P0 controls for live trading safety.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Valid execution stages, in promotion order. Paper-first is the hard default.
EXECUTION_STAGES = ("paper", "advisory", "bounded_autonomous")
_DEFAULT_POLICY_PATH = Path(__file__).parent / "data" / "execution_policy.json"


@dataclass
class RiskLimits:
    """Configurable risk limits from config.json trading.risk_limits."""

    max_position_pct: float = 0.02  # Kelly capped at 2%
    max_portfolio_drawdown_pct: float = 0.10  # 10% max drawdown
    max_daily_loss_pct: float = 0.03  # 3% daily loss limit
    regime_shift_halt: bool = True
    require_human_approval_live: bool = True
    # Staged execution gating (CONCEPT:EE-038). Paper-first by default; only
    # ``bounded_autonomous`` may submit live, and only within these caps.
    stage: str = "paper"
    max_notional_per_trade: float = 0.0  # 0 ⇒ unset (no per-trade cap beyond pct)
    max_daily_notional: float = 0.0
    require_human_above: float = 0.0  # bounded-auto orders above this need approval
    prediction_market_cost_thresholds: dict[str, float] = field(
        default_factory=lambda: {"polymarket": 0.08, "kalshi": 0.08}
    )

    @classmethod
    def from_execution_policy(cls, policy: dict[str, Any]) -> "RiskLimits":
        """Build limits from an execution-policy dict (see execution_policy.json).

        ``paper``/``advisory`` keep ``require_human_approval_live=True`` so live
        orders are blocked; ``bounded_autonomous`` sets it False and relies on the
        notional caps. Stage promotion is a human action — never inferred here.
        """
        stage = str(policy.get("stage", "paper"))
        if stage not in EXECUTION_STAGES:
            logger.warning("unknown execution stage %r; forcing 'paper'", stage)
            stage = "paper"
        caps = policy.get("bounded_autonomous", {}) or {}
        return cls(
            stage=stage,
            require_human_approval_live=(stage != "bounded_autonomous"),
            max_notional_per_trade=float(caps.get("max_notional_per_trade", 0.0)),
            max_daily_notional=float(caps.get("max_daily_notional", 0.0)),
            require_human_above=float(caps.get("require_human_above", 0.0)),
        )


def load_execution_policy(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """Load the execution policy JSON (CONCEPT:EE-038), defaulting to paper.

    Returns ``{"stage": "paper", ...}`` when the file is absent or malformed, so
    the system fails safe to paper trading rather than to an open stage.
    """
    p = Path(path) if path else _DEFAULT_POLICY_PATH
    try:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — fail safe to paper
        logger.warning("execution policy load failed (%s); defaulting to paper", exc)
    return {"stage": "paper"}


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str
    adjusted_qty: float = 0.0
    risk_score: float = 0.0  # 0.0 = safe, 1.0 = max risk


class RiskGuard:
    """Pre-trade and runtime risk validation engine. CONCEPT:EE-007."""

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()
        self._daily_pnl: float = 0.0
        self._peak_equity: float = 0.0
        self._halted: bool = False

    @property
    def is_halted(self) -> bool:
        return self._halted

    def halt(self, reason: str = "Manual kill switch") -> None:
        """Emergency kill switch — CONCEPT:OS-5.1."""
        self._halted = True
        logger.critical("🛑 TRADING HALTED: %s", reason)

    def resume(self) -> None:
        self._halted = False
        logger.warning("⚠️ Trading resumed — ensure conditions are safe")

    def evaluate_graduation(
        self, metrics: dict[str, Any], policy: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Report whether the current stage is ELIGIBLE to advance (CONCEPT:EE-038).

        Read-only: it never changes the stage — promotion is a human action via
        :meth:`approve_stage`. ``metrics`` carries observed performance (e.g.
        ``paper_trades``, ``deflated_sharpe``, ``pbo``, ``hit_rate``,
        ``approved_advisories``, ``live_sharpe``, ``max_drawdown_pct``). Thresholds
        come from the policy's ``graduation`` block.
        """
        policy = policy or load_execution_policy()
        grad = policy.get("graduation", {}) or {}
        stage = self.limits.stage
        if stage == "paper":
            req = grad.get("paper_to_advisory", {})
            unmet = []
            if metrics.get("paper_trades", 0) < req.get("min_paper_trades", 0):
                unmet.append("min_paper_trades")
            if metrics.get("deflated_sharpe", 0.0) < req.get("min_deflated_sharpe", 0.0):
                unmet.append("min_deflated_sharpe")
            if metrics.get("pbo", 1.0) > req.get("max_pbo", 1.0):
                unmet.append("max_pbo")
            if metrics.get("hit_rate", 0.0) < req.get("min_hit_rate", 0.0):
                unmet.append("min_hit_rate")
            return {"stage": stage, "next": "advisory", "eligible": not unmet, "unmet": unmet}
        if stage == "advisory":
            req = grad.get("advisory_to_bounded", {})
            unmet = []
            if metrics.get("approved_advisories", 0) < req.get("min_approved_advisories", 0):
                unmet.append("min_approved_advisories")
            if metrics.get("live_sharpe", 0.0) < req.get("min_live_sharpe", 0.0):
                unmet.append("min_live_sharpe")
            if metrics.get("max_drawdown_pct", 1.0) > req.get("max_drawdown_pct", 1.0):
                unmet.append("max_drawdown_pct")
            return {"stage": stage, "next": "bounded_autonomous", "eligible": not unmet, "unmet": unmet}
        return {"stage": stage, "next": None, "eligible": False, "unmet": ["already at terminal stage"]}

    def approve_stage(self, new_stage: str, token: str) -> bool:
        """Promote the execution stage — a HUMAN action gated by a secret token.

        Requires ``token`` to match ``EMERALD_STAGE_APPROVAL_TOKEN`` from the
        environment. The agent itself can never call this successfully (it has no
        token), enforcing the "never self-escalate" rule. Returns True on success.
        """
        if new_stage not in EXECUTION_STAGES:
            logger.error("approve_stage: unknown stage %r", new_stage)
            return False
        expected = os.getenv("EMERALD_STAGE_APPROVAL_TOKEN", "")
        if not expected or token != expected:
            logger.error("approve_stage: invalid or missing approval token")
            return False
        self.limits.stage = new_stage
        self.limits.require_human_approval_live = new_stage != "bounded_autonomous"
        logger.warning("✅ Execution stage promoted to %s (human-approved)", new_stage)
        return True

    def pre_trade_check(
        self,
        symbol: str,
        qty: float,
        price: float,
        portfolio_equity: float,
        portfolio_cash: float,
        is_live: bool = False,
    ) -> RiskCheckResult:
        """Validate order before submission. Returns approval + adjusted qty."""
        if self._halted:
            return RiskCheckResult(False, "Trading is halted (kill switch active)")

        if is_live and self.limits.require_human_approval_live:
            return RiskCheckResult(False, "Live trading requires human approval")

        # Staged execution gate (CONCEPT:EE-038). Only bounded_autonomous may
        # submit live, and only within the policy's notional caps.
        if is_live:
            position_value = qty * price
            if self.limits.stage != "bounded_autonomous":
                return RiskCheckResult(
                    False,
                    f"{self.limits.stage} stage does not permit live orders "
                    "(paper-first; promote the stage to go live)",
                )
            if (
                self.limits.require_human_above > 0
                and position_value > self.limits.require_human_above
            ):
                return RiskCheckResult(
                    False,
                    f"Order ${position_value:.2f} exceeds autonomous cap "
                    f"${self.limits.require_human_above:.2f}; human approval required",
                )
            if (
                self.limits.max_notional_per_trade > 0
                and position_value > self.limits.max_notional_per_trade
            ):
                return RiskCheckResult(
                    False,
                    f"Order ${position_value:.2f} exceeds per-trade notional cap "
                    f"${self.limits.max_notional_per_trade:.2f}",
                )

        # Position size check (Kelly cap)
        position_value = qty * price
        position_pct = (
            position_value / portfolio_equity if portfolio_equity > 0 else 1.0
        )
        if position_pct > self.limits.max_position_pct:
            max_qty = (self.limits.max_position_pct * portfolio_equity) / price
            return RiskCheckResult(
                approved=True,
                reason=f"Position sized down: {position_pct:.1%} > {self.limits.max_position_pct:.1%} limit",
                adjusted_qty=max_qty,
                risk_score=position_pct / self.limits.max_position_pct,
            )

        # Cash check
        if position_value > portfolio_cash:
            return RiskCheckResult(
                False,
                f"Insufficient cash: need ${position_value:.2f}, have ${portfolio_cash:.2f}",
            )

        return RiskCheckResult(
            True,
            "Approved",
            adjusted_qty=qty,
            risk_score=position_pct / self.limits.max_position_pct,
        )

    def check_drawdown(self, current_equity: float) -> RiskCheckResult:
        """Check portfolio drawdown against limits."""
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        if self._peak_equity <= 0:
            return RiskCheckResult(True, "No peak established yet")

        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        if drawdown >= self.limits.max_portfolio_drawdown_pct:
            self.halt(
                f"Max drawdown breached: {drawdown:.1%} >= {self.limits.max_portfolio_drawdown_pct:.1%}"
            )
            return RiskCheckResult(
                False, f"CIRCUIT BREAKER: Drawdown {drawdown:.1%}", risk_score=1.0
            )

        return RiskCheckResult(
            True,
            f"Drawdown OK: {drawdown:.1%}",
            risk_score=drawdown / self.limits.max_portfolio_drawdown_pct,
        )

    def check_daily_loss(
        self, daily_pnl: float, portfolio_equity: float
    ) -> RiskCheckResult:
        """Check daily loss limit."""
        self._daily_pnl = daily_pnl
        if portfolio_equity <= 0:
            return RiskCheckResult(False, "No portfolio equity")

        daily_loss_pct = abs(min(0, daily_pnl)) / portfolio_equity
        if daily_loss_pct >= self.limits.max_daily_loss_pct:
            self.halt(f"Daily loss limit breached: {daily_loss_pct:.1%}")
            return RiskCheckResult(
                False,
                f"CIRCUIT BREAKER: Daily loss {daily_loss_pct:.1%}",
                risk_score=1.0,
            )

        return RiskCheckResult(
            True,
            f"Daily P&L: ${daily_pnl:.2f}",
            risk_score=daily_loss_pct / self.limits.max_daily_loss_pct,
        )

    @staticmethod
    def check_regime_shift(
        historical: np.ndarray, recent: np.ndarray, threshold: float = 0.1
    ) -> bool:
        """KS-test for regime shift detection."""
        if len(historical) < 20 or len(recent) < 5:
            return False
        try:
            from scipy.stats import ks_2samp

            stat, _ = ks_2samp(historical, recent)
            return stat > threshold
        except ImportError:
            logger.warning("scipy not available for regime shift detection")
            return False

    @staticmethod
    def kelly_criterion(
        win_rate: float,
        win_loss_ratio: float,
        half_kelly: bool = True,
        max_risk: float = 0.02,
    ) -> float:
        """Calculate point Kelly criterion position size."""
        if win_loss_ratio <= 0:
            return 0.0
        f_star = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        if half_kelly:
            f_star /= 2.0
        return max(0.0, min(f_star, max_risk))

    def bayesian_kelly_size(
        self,
        wins: int,
        losses: int,
        cost: float,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        fraction: float = 0.25,
    ) -> float:
        """Bayesian-Kelly sizing under a Beta(α, β) posterior — CONCEPT:EE-015.

        Unlike :meth:`kelly_criterion` (a point estimate of the edge), this path
        accounts for *estimation uncertainty*: it builds a Beta posterior over the
        true win probability from observed ``wins``/``losses`` plus a prior, then
        delegates to the Rust engine's ``bayesian_kelly`` (which integrates Kelly
        over that posterior and shrinks the bet as posterior variance grows).

        Delegates compute to ``epistemic_graph`` ``client.finance.bayesian_kelly``;
        falls back to the point Kelly cap when the engine is unreachable so that
        sizing is never silently zeroed offline. The result is always clamped to
        ``[0, max_position_pct]`` — the same cap the point path respects.

        Args:
            wins: observed winning bets (Beta successes).
            losses: observed losing bets (Beta failures).
            cost: per-contract cost ``c`` in (0, 1) — the YES entry price.
            prior_alpha / prior_beta: Beta prior pseudo-counts.
            fraction: fractional-Kelly scaler (e.g. 0.25 = quarter Kelly).

        Returns:
            Capped fraction of capital to allocate, in [0, max_position_pct].
        """
        alpha = prior_alpha + max(0, int(wins))
        beta = prior_beta + max(0, int(losses))
        cap = self.limits.max_position_pct

        from emerald_exchange._engine import finance_engine

        engine = finance_engine()
        if engine is not None:
            try:
                f = float(
                    engine.finance.bayesian_kelly(alpha, beta, cost, n_quadrature=50)
                )
                f *= fraction
                return max(0.0, min(f, cap))
            except Exception as exc:  # noqa: BLE001 — degrade to point Kelly
                logger.debug("bayesian_kelly engine call failed: %s", exc)

        # Engine-free fallback: point Kelly from the posterior mean win-rate.
        win_rate = alpha / (alpha + beta)
        win_loss_ratio = (1.0 - cost) / cost if 0 < cost < 1 else 1.0
        f_star = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        return max(0.0, min(f_star * fraction, cap))

    def empirical_kelly_size(
        self,
        p: float,
        b: float,
        historical_returns: list[float],
        fraction: float = 0.25,
        n_simulations: int = 10000,
        seed: int = 42,
    ) -> float:
        """Empirical (Monte-Carlo resampled) Kelly sizing — CONCEPT:EE-031.

        Where :meth:`kelly_criterion` uses the textbook closed form and
        :meth:`bayesian_kelly_size` integrates over a Beta posterior, this path
        sizes against the *realized return distribution*: it resamples the
        observed per-bet ``historical_returns`` to find the growth-optimal
        fraction, so fat tails / skew in the actual P&L (not just win-rate) shrink
        the bet. Delegates compute to ``client.finance.empirical_kelly``.

        Composition with the existing sizing ladder: this returns a *raw* Kelly
        fraction that is fractional-scaled and then clamped to
        ``[0, max_position_pct]`` — the SAME cap the point/Bayesian paths respect,
        so it slots in as a drop-in third estimator without weakening the position
        cap. Falls back to the point Kelly cap when the engine is unreachable so
        sizing is never silently zeroed offline.

        Args:
            p: win probability estimate.
            b: net win odds (payoff per unit risked on a win).
            historical_returns: observed per-bet returns to resample.
            fraction: fractional-Kelly scaler (e.g. 0.25 = quarter Kelly).
            n_simulations: Monte-Carlo resamples.
            seed: RNG seed for reproducibility.

        Returns:
            Capped fraction of capital to allocate, in [0, max_position_pct].
        """
        cap = self.limits.max_position_pct

        from emerald_exchange._engine import finance_engine

        engine = finance_engine()
        if engine is not None and historical_returns:
            try:
                f = float(
                    engine.finance.empirical_kelly(
                        p, b, historical_returns, n_simulations, seed
                    )
                )
                return max(0.0, min(f * fraction, cap))
            except Exception as exc:  # noqa: BLE001 — degrade to point Kelly
                logger.debug("empirical_kelly engine call failed: %s", exc)

        # Engine-free / no-history fallback: point Kelly from (p, b).
        if b <= 0:
            return 0.0
        f_star = (p * b - (1.0 - p)) / b
        return max(0.0, min(f_star * fraction, cap))
