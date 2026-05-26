"""Risk Management MCP Tools — CONCEPT:EE-011 / OS-5.1."""

from typing import Any

import json

from emerald_exchange.backends import ExchangeBackend
from emerald_exchange.risk_guards import RiskGuard


def register_risk_tools(
    mcp: Any, backend: ExchangeBackend, risk_guard: RiskGuard
) -> None:

    @mcp.tool(tags=["risk"])
    def emerald_risk(
        action: str,
        daily_pnl: float = 0.0,
        win_rate: float = 0.5,
        win_loss_ratio: float = 1.5,
    ) -> str:
        """Risk management and monitoring. CONCEPT:EE-011

        Actions:
        - 'status': Current risk status (halted?, drawdown, daily PnL)
        - 'drawdown_check': Check portfolio drawdown against limits
        - 'daily_loss_check': Check daily loss against limits
        - 'kelly': Calculate Kelly criterion position size
        - 'limits': Show current risk limits configuration
        """
        if action == "status":
            acct = backend.get_account()
            return json.dumps(
                {
                    "halted": risk_guard.is_halted,
                    "equity": acct.equity,
                    "peak_equity": risk_guard._peak_equity,
                    "exchange": backend.name,
                    "mode": backend.mode,
                }
            )
        elif action == "drawdown_check":
            acct = backend.get_account()
            check = risk_guard.check_drawdown(acct.equity)
            return json.dumps(
                {
                    "approved": check.approved,
                    "reason": check.reason,
                    "risk_score": check.risk_score,
                    "halted": risk_guard.is_halted,
                }
            )
        elif action == "daily_loss_check":
            acct = backend.get_account()
            check = risk_guard.check_daily_loss(daily_pnl, acct.equity)
            return json.dumps(
                {
                    "approved": check.approved,
                    "reason": check.reason,
                    "risk_score": check.risk_score,
                    "halted": risk_guard.is_halted,
                }
            )
        elif action == "kelly":
            size = risk_guard.kelly_criterion(win_rate, win_loss_ratio)
            return json.dumps(
                {
                    "kelly_fraction": size,
                    "max_position_pct": risk_guard.limits.max_position_pct,
                }
            )
        elif action == "limits":
            lim = risk_guard.limits
            return json.dumps(
                {
                    "max_position_pct": lim.max_position_pct,
                    "max_portfolio_drawdown_pct": lim.max_portfolio_drawdown_pct,
                    "max_daily_loss_pct": lim.max_daily_loss_pct,
                    "regime_shift_halt": lim.regime_shift_halt,
                    "require_human_approval_live": lim.require_human_approval_live,
                }
            )
        return json.dumps({"error": f"Unknown action: {action}"})
