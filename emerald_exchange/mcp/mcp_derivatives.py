"""Derivatives / SABR MCP Tools — CONCEPT:AU-AHE.assimilation.decision-distillation.

One typed tool per operation over the engine's SABR volatility-surface
kernels (``client.finance.sabr_*``, KG-2.20j / DSCI-007) plus a vol-arb helper
that diffs a market smile against the SABR-fair smile.

All compute runs in the Rust ``medulla`` engine; this stays thin and
degrades gracefully (``{"error": ...}``) when the engine socket is unreachable.
The vol-arb tool is decision-only — it surfaces rich/cheap strikes, never an
order.
"""

import json
import logging
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import Field

from emerald_exchange.mcp._hints import READ

logger = logging.getLogger(__name__)

Forward = Annotated[float, Field(description="Forward price f")]
Expiry = Annotated[float, Field(description="Time to expiry t in years")]
Strikes = Annotated[list[float], Field(description="Strike prices")]
MarketVols = Annotated[
    list[float], Field(description="Market implied vols, one per strike")
]
Alpha = Annotated[float, Field(description="SABR alpha")]
Beta = Annotated[float, Field(description="SABR beta (CEV exponent)")]
Rho = Annotated[float, Field(description="SABR rho")]
Nu = Annotated[float, Field(description="SABR nu (vol of vol)")]


def _run(compute: Callable[[], Any]) -> str:
    try:
        return json.dumps(compute())
    except Exception as exc:  # noqa: BLE001
        logger.error("Derivatives tool error: error_type=%s", type(exc).__name__)
        return json.dumps({"error": "Operation failed"})


def register_derivatives_tools(mcp: Any) -> None:
    """Register the SABR derivatives tools."""
    from emerald_exchange import analyses as derivatives

    @mcp.tool(tags={"derivatives"}, annotations=READ)
    def emerald_derivatives_implied_vol(
        f: Forward,
        k: Annotated[float, Field(description="Strike k")],
        t: Expiry,
        alpha: Alpha,
        beta: Beta = 0.5,
        rho: Rho = 0.0,
        nu: Nu = 0.0,
    ) -> str:
        """One-strike SABR implied vol. CONCEPT:AU-AHE.assimilation.decision-distillation"""
        return _run(
            lambda: derivatives.implied_vol(
                f=f, k=k, t=t, alpha=alpha, beta=beta, rho=rho, nu=nu
            )
        )

    @mcp.tool(tags={"derivatives"}, annotations=READ)
    def emerald_derivatives_smile(
        f: Forward,
        strikes: Strikes,
        t: Expiry,
        alpha: Alpha,
        beta: Beta = 0.5,
        rho: Rho = 0.0,
        nu: Nu = 0.0,
    ) -> str:
        """SABR implied-vol smile across strikes. CONCEPT:AU-AHE.assimilation.decision-distillation"""
        return _run(
            lambda: derivatives.smile(
                f=f, strikes=strikes, t=t, alpha=alpha, beta=beta, rho=rho, nu=nu
            )
        )

    @mcp.tool(tags={"derivatives"}, annotations=READ)
    def emerald_derivatives_calibrate(
        f: Forward,
        t: Expiry,
        strikes: Strikes,
        market_vols: MarketVols,
        beta: Beta = 0.5,
    ) -> str:
        """Calibrate SABR (alpha, rho, nu) to a market smile with beta fixed.

        Returns {alpha, beta, rho, nu, rmse, converged}.
        CONCEPT:AU-AHE.assimilation.decision-distillation
        """
        return _run(
            lambda: derivatives.calibrate(
                f=f, t=t, strikes=strikes, market_vols=market_vols, beta=beta
            )
        )

    @mcp.tool(tags={"derivatives"}, annotations=READ)
    def emerald_derivatives_vol_arb(
        f: Forward,
        t: Expiry,
        strikes: Strikes,
        market_vols: MarketVols,
        beta: Beta = 0.5,
    ) -> str:
        """Rich/cheap strikes against the SABR-fair smile (decision only).

        Refused (not_served) until medulla serves it.
        CONCEPT:AU-AHE.assimilation.decision-distillation
        """
        return _run(
            lambda: derivatives.vol_arb(
                f=f, t=t, strikes=strikes, market_vols=market_vols, beta=beta
            )
        )
