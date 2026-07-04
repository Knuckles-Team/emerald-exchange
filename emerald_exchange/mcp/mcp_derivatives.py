"""Derivatives / SABR MCP Tools — CONCEPT:AU-AHE.assimilation.decision-distillation.

Action-routed tool exposing the engine's SABR volatility-surface kernels
(``client.finance.sabr_*``, KG-2.20j / DSCI-007) plus a vol-arb helper that
diffs a market smile against the SABR-fair smile.

All compute runs in the Rust ``epistemic-graph`` engine; this stays thin and
degrades gracefully (``{"error": ...}``) when the engine socket is unreachable.
The vol-arb action is decision-only — it surfaces rich/cheap strikes, never an
order.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_derivatives_tools(mcp: Any) -> None:
    """Register the ``emerald_derivatives`` SABR tool."""

    @mcp.tool(tags=["derivatives"])
    def emerald_derivatives(
        action: str,
        params_json: str = "{}",
    ) -> str:
        """SABR volatility surface + vol-arb. CONCEPT:AU-AHE.assimilation.decision-distillation

        Actions:
          - 'implied_vol': one-strike SABR implied vol. params: f, k, t, alpha,
            beta, rho, nu.
          - 'smile': SABR implied-vol smile across strikes. params: f,
            strikes (list), t, alpha, beta, rho, nu.
          - 'calibrate': calibrate SABR (α, ρ, ν) to a market smile with β
            fixed. params: f, t, strikes (list), market_vols (list), beta.
            Returns {alpha, beta, rho, nu, rmse, converged}.
          - 'vol_arb': calibrate then compare market vs SABR-fair smile,
            flagging rich (sell-vol) / cheap (buy-vol) strikes. params: f, t,
            strikes (list), market_vols (list), beta. Decision-only.

        Args:
            action: operation to perform.
            params_json: JSON string of parameters.
        """
        try:
            params = json.loads(params_json or "{}")
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"invalid params_json: {exc}"})

        from emerald_exchange import derivatives

        try:
            if action == "implied_vol":
                return json.dumps(
                    derivatives.implied_vol(
                        f=float(params.get("f", 0.0)),
                        k=float(params.get("k", 0.0)),
                        t=float(params.get("t", 0.0)),
                        alpha=float(params.get("alpha", 0.0)),
                        beta=float(params.get("beta", 0.5)),
                        rho=float(params.get("rho", 0.0)),
                        nu=float(params.get("nu", 0.0)),
                    )
                )
            if action == "smile":
                return json.dumps(
                    derivatives.smile(
                        f=float(params.get("f", 0.0)),
                        strikes=[float(s) for s in params.get("strikes", [])],
                        t=float(params.get("t", 0.0)),
                        alpha=float(params.get("alpha", 0.0)),
                        beta=float(params.get("beta", 0.5)),
                        rho=float(params.get("rho", 0.0)),
                        nu=float(params.get("nu", 0.0)),
                    )
                )
            if action == "calibrate":
                return json.dumps(
                    derivatives.calibrate(
                        f=float(params.get("f", 0.0)),
                        t=float(params.get("t", 0.0)),
                        strikes=[float(s) for s in params.get("strikes", [])],
                        market_vols=[float(v) for v in params.get("market_vols", [])],
                        beta=float(params.get("beta", 0.5)),
                    )
                )
            if action == "vol_arb":
                return json.dumps(
                    derivatives.vol_arb(
                        f=float(params.get("f", 0.0)),
                        t=float(params.get("t", 0.0)),
                        strikes=[float(s) for s in params.get("strikes", [])],
                        market_vols=[float(v) for v in params.get("market_vols", [])],
                        beta=float(params.get("beta", 0.5)),
                    )
                )
            return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as exc:  # noqa: BLE001
            logger.error("derivatives tool error: %s", exc)
            return json.dumps({"error": str(exc)})
