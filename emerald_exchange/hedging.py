"""Dynamic-Beta Hedging — CONCEPT:EX-AHE.harness.ee-28.

A thin controller over the Rust ``epistemic-graph`` engine's time-varying CAPM
Kalman-beta kernel (``client.finance.kalman_beta``, KG-2.20h). Given an asset's
return series and a market/benchmark return series, it estimates the *current*
(latest) hedge beta together with the filter's posterior variance, and returns
the beta-neutral hedge ratio plus a 1-sigma uncertainty band.

emerald-exchange owns no Kalman math — all compute is delegated to the engine.
Importing this module never requires a running engine; when the engine is
unreachable (or a stale daemon lacks the kernel) the call degrades cleanly to an
``{"error": ...}`` payload.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from emerald_exchange._engine import ENGINE_REQUIRED_ERR, finance_engine

logger = logging.getLogger(__name__)


def dynamic_beta_hedge(
    asset_returns: list[float],
    market_returns: list[float],
    q: float = 1e-5,
    r: float = 1e-3,
    beta0: float = 1.0,
    p0: float = 1.0,
    n_sigma: float = 1.0,
) -> dict[str, Any]:
    """Estimate the current beta-neutral hedge ratio via Kalman beta. CONCEPT:EX-AHE.harness.ee-28.

    Runs the engine's ``kalman_beta`` over the paired (market, asset) return
    series and reads the *last* state as the current beta. The hedge ratio for a
    beta-neutral position is ``-beta`` units of the market instrument per unit of
    the asset (short the market when long the asset for a positive beta).

    Args:
        asset_returns: per-period returns of the asset being hedged.
        market_returns: per-period returns of the market/benchmark instrument.
        q: Kalman process-noise variance (how fast beta is allowed to drift).
        r: Kalman observation-noise variance.
        beta0 / p0: initial beta and its prior variance.
        n_sigma: width of the uncertainty band in posterior std-devs.

    Returns:
        ``{beta, beta_variance, beta_std, hedge_ratio, hedge_ratio_lower,
        hedge_ratio_upper, n_obs, engine_used}`` or ``{"error": ...}`` when the
        engine is unreachable, the kernel is missing, or the inputs are invalid.
    """
    if len(asset_returns) != len(market_returns):
        return {
            "error": (
                "asset_returns and market_returns must be the same length "
                f"({len(asset_returns)} != {len(market_returns)})"
            )
        }
    if len(asset_returns) < 2:
        return {"error": "need at least 2 paired observations to estimate beta"}

    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}

    try:
        out = engine.finance.kalman_beta(market_returns, asset_returns, q, r, beta0, p0)
    except Exception as exc:  # noqa: BLE001 — degrade cleanly (incl. stale daemon)
        logger.debug("Operation failed: error_type=%s", type(exc).__name__)
        return {"error": "Operation failed"}

    states = out.get("states") if isinstance(out, dict) else None
    variances = out.get("variances") if isinstance(out, dict) else None
    if not states:
        return {"error": "kalman_beta returned no states"}

    beta = float(states[-1])
    beta_var = float(variances[-1]) if variances else 0.0
    beta_std = math.sqrt(max(beta_var, 0.0))

    # Beta-neutral hedge ratio: short `beta` units of market per unit of asset.
    hedge_ratio = -beta
    band = n_sigma * beta_std
    return {
        "beta": beta,
        "beta_variance": beta_var,
        "beta_std": beta_std,
        "hedge_ratio": hedge_ratio,
        "hedge_ratio_lower": -(beta + band),
        "hedge_ratio_upper": -(beta - band),
        "n_sigma": n_sigma,
        "n_obs": len(asset_returns),
        "engine_used": True,
    }
