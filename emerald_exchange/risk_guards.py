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
        """Calculate Kelly criterion position size."""
        if win_loss_ratio <= 0:
            return 0.0
        f_star = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        if half_kelly:
            f_star /= 2.0
        return max(0.0, min(f_star, max_risk))
