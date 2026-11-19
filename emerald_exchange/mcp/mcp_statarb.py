"""Statistical-Arbitrage / Dynamic-Beta Hedging MCP Tools.

CONCEPT:EX-AHE.harness.ee-28 (dynamic-beta hedge) / EE-030 (OU stat-arb).

One typed tool per medulla analysis (``ontology/quant.ttl``):
  - ``emerald_statarb_ou_signal``: spread → ADF stationarity, OU calibration
    and optimal entry/exit bands (SpreadStationarityAnalysis,
    MeanReversionCalibrationAnalysis, MeanReversionThresholdAnalysis).
  - ``emerald_statarb_dynamic_beta``: asset + market returns → Kalman hedge
    beta (HedgeBetaAnalysis).

CRITICAL SAFETY: both tools return measurements only; they never place
orders. Live execution stays gated behind ``RiskGuard.require_human_approval_live``.
"""

import json
import logging
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import Field

from emerald_exchange.mcp._hints import READ

logger = logging.getLogger(__name__)

Returns = Annotated[list[float], Field(description="Return series")]


def _run(compute: Callable[[], Any]) -> str:
    try:
        return json.dumps(compute())
    except Exception as exc:  # noqa: BLE001
        logger.error("Statarb tool error: error_type=%s", type(exc).__name__)
        return json.dumps({"error": "Operation failed"})


def register_statarb_tools(mcp: Any) -> None:
    """Register the stat-arb / dynamic-beta hedging tools."""
    from emerald_exchange import analyses

    @mcp.tool(tags={"statarb"}, annotations=READ)
    def emerald_statarb_ou_signal(
        spread: Annotated[list[float], Field(description="Spread series")],
        dt: Annotated[float, Field(description="Sampling interval")] = 1.0,
        adf_max_lag: Annotated[int, Field(description="ADF maximum lag")] = 1,
        cost: Annotated[float, Field(description="Round-trip trading cost")] = 0.0,
    ) -> str:
        """OU stat-arb bands: {adf, ou, thresholds} from medulla. CONCEPT:EX-AHE.harness.ee-29"""
        return _run(
            lambda: analyses.ou_stat_arb_signal(
                spread=spread, dt=dt, adf_max_lag=adf_max_lag, cost=cost
            )
        )

    @mcp.tool(tags={"statarb"}, annotations=READ)
    def emerald_statarb_dynamic_beta(
        asset_returns: Returns,
        market_returns: Returns,
        q: Annotated[float, Field(description="Process noise")] = 1e-5,
        r: Annotated[float, Field(description="Observation noise")] = 1e-3,
        beta0: Annotated[float, Field(description="Initial beta")] = 1.0,
        p0: Annotated[float, Field(description="Initial beta variance")] = 1.0,
    ) -> str:
        """Current Kalman hedge beta and its variance. CONCEPT:EX-AHE.harness.ee-28"""
        return _run(
            lambda: analyses.dynamic_beta_hedge(
                asset_returns=asset_returns,
                market_returns=market_returns,
                q=q,
                r=r,
                beta0=beta0,
                p0=p0,
            )
        )
