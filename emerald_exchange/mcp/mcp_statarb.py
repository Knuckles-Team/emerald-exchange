"""Statistical-Arbitrage / Dynamic-Beta Hedging MCP Tools.

CONCEPT:EE-029 (dynamic-beta hedge) / EE-030 (OU stat-arb signal).

Action-routed tool exposing two engine-backed stat-arb surfaces:
  - 'ou_signal': two venues' price series for the same outcome → spread → ADF
    stationarity gate → OU calibration + thresholds → entry/exit signal.
  - 'dynamic_beta': asset + market return series → current Kalman beta →
    beta-neutral hedge ratio + uncertainty band.

CRITICAL SAFETY: both actions return *decisions* only; they never place orders.
Live execution stays gated behind ``RiskGuard.require_human_approval_live``.
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
        """OU statistical-arbitrage signal + dynamic-beta hedge. CONCEPT:EE-030

        Actions:
          - 'ou_signal': OU stat-arb entry/exit signal between two venues.
            params: px_a (list), px_b (list), hedge_ratio (float, default 1.0),
            dt (float), adf_max_lag (int), cost (float),
            require_stationary (bool, default true). Builds the spread, gates on
            ADF stationarity, OU-calibrates, derives optimal thresholds, and
            emits entry_long/entry_short/exit/hold/no_trade (decision only).
          - 'dynamic_beta': beta-neutral hedge ratio via Kalman beta.
            params: asset_returns (list), market_returns (list), q, r, beta0, p0,
            n_sigma (float, default 1.0). Returns the current beta, its variance,
            the hedge ratio (-beta), and a ±n_sigma uncertainty band.

        Args:
            action: operation to perform.
            params_json: JSON string of parameters.
        """
        try:
            params = json.loads(params_json or "{}")
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"invalid params_json: {exc}"})

        try:
            if action == "ou_signal":
                from emerald_exchange.stat_arb import ou_stat_arb_signal

                result = ou_stat_arb_signal(
                    px_a=params.get("px_a", []),
                    px_b=params.get("px_b", []),
                    hedge_ratio=float(params.get("hedge_ratio", 1.0)),
                    dt=float(params.get("dt", 1.0)),
                    adf_max_lag=int(params.get("adf_max_lag", 1)),
                    cost=float(params.get("cost", 0.0)),
                    require_stationary=bool(params.get("require_stationary", True)),
                )
                return json.dumps(result)

            elif action == "dynamic_beta":
                from emerald_exchange.hedging import dynamic_beta_hedge

                result = dynamic_beta_hedge(
                    asset_returns=params.get("asset_returns", []),
                    market_returns=params.get("market_returns", []),
                    q=float(params.get("q", 1e-5)),
                    r=float(params.get("r", 1e-3)),
                    beta0=float(params.get("beta0", 1.0)),
                    p0=float(params.get("p0", 1.0)),
                    n_sigma=float(params.get("n_sigma", 1.0)),
                )
                return json.dumps(result)

            return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as exc:  # noqa: BLE001
            logger.error("statarb tool error: %s", exc)
            return json.dumps({"error": str(exc)})
