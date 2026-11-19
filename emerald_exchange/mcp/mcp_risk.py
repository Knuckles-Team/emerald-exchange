"""Risk Management MCP Tools — CONCEPT:AU-AHE.assimilation.skill-workflow-ingest / OS-5.1.

One typed tool per risk operation. Kelly sizes are run by medulla; an
unreachable engine or an unserved analysis returns its error payload.
"""

import json
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import Field

from emerald_exchange.backends import ExchangeBackend
from emerald_exchange.mcp._hints import READ
from emerald_exchange.risk_guards import RiskGuard

Fraction = Annotated[float, Field(description="Fraction of full Kelly to use")]


def _engine_backed(compute: Callable[[], dict[str, Any]]) -> str:
    """Run a medulla-backed sizing; engine refusals become their error payload."""
    from scion_sdk.compute import ComputeUnavailableError, MethodNotServedError

    from emerald_exchange._engine import engine_error

    try:
        return json.dumps(compute())
    except (ComputeUnavailableError, MethodNotServedError) as exc:
        return json.dumps(engine_error(exc))


def register_risk_tools(
    mcp: Any, backend: ExchangeBackend, risk_guard: RiskGuard
) -> None:
    """Register the risk tools. CONCEPT:AU-AHE.assimilation.skill-workflow-ingest"""

    def _check(check: Any) -> str:
        return json.dumps(
            {
                "approved": check.approved,
                "reason": check.reason,
                "risk_score": check.risk_score,
                "halted": risk_guard.is_halted,
            }
        )

    @mcp.tool(tags={"risk"}, annotations=READ)
    def emerald_risk_status() -> str:
        """Current risk status: halted, equity and peak equity."""
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

    @mcp.tool(tags={"risk"}, annotations=READ)
    def emerald_risk_drawdown_check() -> str:
        """Check portfolio drawdown against the configured limit."""
        return _check(risk_guard.check_drawdown(backend.get_account().equity))

    @mcp.tool(tags={"risk"}, annotations=READ)
    def emerald_risk_daily_loss_check(
        daily_pnl: Annotated[float, Field(description="Today's profit and loss")],
    ) -> str:
        """Check the daily loss against the configured limit."""
        acct = backend.get_account()
        return _check(risk_guard.check_daily_loss(daily_pnl, acct.equity))

    @mcp.tool(tags={"risk"}, annotations=READ)
    def emerald_risk_kelly(
        win_rate: Annotated[float, Field(description="Win probability")] = 0.5,
        win_loss_ratio: Annotated[float, Field(description="Average win / loss")] = 1.5,
    ) -> str:
        """Point Kelly criterion position size."""
        return _engine_backed(
            lambda: {
                "kelly_fraction": risk_guard.kelly_criterion(win_rate, win_loss_ratio),
                "max_position_pct": risk_guard.limits.max_position_pct,
            }
        )

    @mcp.tool(tags={"risk"}, annotations=READ)
    def emerald_risk_bayesian_kelly(
        wins: Annotated[int, Field(description="Observed wins")] = 0,
        losses: Annotated[int, Field(description="Observed losses")] = 0,
        cost: Annotated[float, Field(description="Contract cost")] = 0.5,
        fraction: Fraction = 0.25,
    ) -> str:
        """Beta-posterior Kelly sizing (engine-backed, uncertainty-aware)."""
        return _engine_backed(
            lambda: {
                "bayesian_kelly_fraction": risk_guard.bayesian_kelly_size(
                    wins=wins, losses=losses, cost=cost, fraction=fraction
                ),
                "wins": wins,
                "losses": losses,
                "cost": cost,
                "fraction": fraction,
                "max_position_pct": risk_guard.limits.max_position_pct,
            }
        )

    @mcp.tool(tags={"risk"}, annotations=READ)
    def emerald_risk_empirical_kelly(
        p: Annotated[float, Field(description="Win probability")] = 0.5,
        b: Annotated[float, Field(description="Net odds")] = 1.0,
        historical_returns: Annotated[
            list[float] | None, Field(description="Realized return distribution")
        ] = None,
        fraction: Fraction = 0.25,
        n_simulations: Annotated[int, Field(description="Monte-Carlo paths")] = 10000,
        seed: Annotated[int, Field(description="Random seed")] = 42,
    ) -> str:
        """Monte-Carlo Kelly sizing over a realized return distribution.

        Engine-backed; capped at max_position_pct.
        """
        history = historical_returns or []
        return _engine_backed(
            lambda: {
                "empirical_kelly_fraction": risk_guard.empirical_kelly_size(
                    p=p,
                    b=b,
                    historical_returns=history,
                    fraction=fraction,
                    n_simulations=n_simulations,
                    seed=seed,
                ),
                "p": p,
                "b": b,
                "n_history": len(history),
                "fraction": fraction,
                "max_position_pct": risk_guard.limits.max_position_pct,
            }
        )

    @mcp.tool(tags={"risk"}, annotations=READ)
    def emerald_risk_limits() -> str:
        """The configured risk limits."""
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
