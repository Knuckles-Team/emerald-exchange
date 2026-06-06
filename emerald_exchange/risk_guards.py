"""Risk Guards — CONCEPT:EE-007 / OS-5.1

Pre-trade risk validation, circuit breakers, and kill switch.
All P0 controls for live trading safety.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Configurable risk limits from config.json trading.risk_limits."""

    max_position_pct: float = 0.02  # Kelly capped at 2%
    max_portfolio_drawdown_pct: float = 0.10  # 10% max drawdown
    max_daily_loss_pct: float = 0.03  # 3% daily loss limit
    regime_shift_halt: bool = True
    require_human_approval_live: bool = True
    prediction_market_cost_thresholds: dict[str, float] = field(
        default_factory=lambda: {"polymarket": 0.08, "kalshi": 0.08}
    )


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
