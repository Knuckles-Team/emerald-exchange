"""Statistical-Arbitrage / Dynamic-Beta Hedging MCP Tools.

CONCEPT:EX-AHE.harness.ee-28 (dynamic-beta hedge) / EE-030 (OU stat-arb).

Action-routed tool over epistemic-graph analyses (``ontology/quant.ttl``):
  - 'ou_signal': spread → ADF stationarity, OU calibration and optimal
    entry/exit bands (SpreadStationarityAnalysis,
    MeanReversionCalibrationAnalysis, MeanReversionThresholdAnalysis).
  - 'dynamic_beta': asset + market returns → Kalman hedge beta
    (HedgeBetaAnalysis).

CRITICAL SAFETY: both actions return measurements only; they never place
orders. Live execution stays gated behind ``RiskGuard.require_human_approval_live``.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_statarb_tools(mcp: Any) -> None:
    """Register the stat-arb / dynamic-beta hedging tool."""

    @mcp.tool(tags=["statarb"])
    def emerald_statarb(
        action: str,
        params_json: str = "{}",
    ) -> str:
        """OU statistical-arbitrage bands + dynamic-beta hedge. CONCEPT:EX-AHE.harness.ee-29

        Actions:
          - 'ou_signal': params: spread (list), dt (float), adf_max_lag (int),
            cost (float). Returns {adf, ou, thresholds} from epistemic-graph.
          - 'dynamic_beta': params: asset_returns (list), market_returns (list),
            q, r, beta0, p0. Returns the current Kalman beta and its variance.

        Args:
            action: operation to perform.
            params_json: JSON string of parameters.
        """
        try:
            params = json.loads(params_json or "{}")
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"invalid params_json: {type(exc).__name__}"})

        from emerald_exchange import analyses

        try:
            if action == "ou_signal":
                return json.dumps(
                    analyses.ou_stat_arb_signal(
                        spread=[float(x) for x in params.get("spread", [])],
                        dt=float(params.get("dt", 1.0)),
                        adf_max_lag=int(params.get("adf_max_lag", 1)),
                        cost=float(params.get("cost", 0.0)),
                    )
                )
            if action == "dynamic_beta":
                return json.dumps(
                    analyses.dynamic_beta_hedge(
                        asset_returns=params.get("asset_returns", []),
                        market_returns=params.get("market_returns", []),
                        q=float(params.get("q", 1e-5)),
                        r=float(params.get("r", 1e-3)),
                        beta0=float(params.get("beta0", 1.0)),
                        p0=float(params.get("p0", 1.0)),
                    )
                )
            return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as exc:  # noqa: BLE001
            logger.error("Statarb tool error: error_type=%s", type(exc).__name__)
            return json.dumps({"error": "Operation failed"})
