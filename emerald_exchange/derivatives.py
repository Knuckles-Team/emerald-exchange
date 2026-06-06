"""SABR volatility-surface helpers — CONCEPT:EE-034

Thin Python seam over the engine's SABR kernels (``client.finance.sabr_*``,
CONCEPT:KG-2.20j / DSCI-007). All compute (Hagan 2002 implied vol, smile,
calibration) runs in the Rust ``epistemic-graph`` engine; this module only
marshals arguments and adds a small vol-arb comparison that diffs a *market*
smile against the SABR-*fair* smile to surface rich/cheap strikes.

Engine is lazy/optional: every function returns an ``{"error": ...}`` payload
when the engine socket is unreachable instead of raising, so importing /
calling never requires a running engine.
"""

from __future__ import annotations

import logging
from typing import Any

from emerald_exchange._engine import ENGINE_REQUIRED_ERR, finance_engine

logger = logging.getLogger(__name__)


def implied_vol(
    f: float,
    k: float,
    t: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> dict[str, Any]:
    """SABR lognormal (Black) implied vol for one strike. CONCEPT:EE-034."""
    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}
    try:
        vol = float(engine.finance.sabr_implied_vol(f, k, t, alpha, beta, rho, nu))
        return {"implied_vol": vol, "f": f, "k": k, "t": t}
    except Exception as exc:  # noqa: BLE001
        logger.debug("sabr_implied_vol failed: %s", exc)
        return {"error": str(exc)}


def smile(
    f: float,
    strikes: list[float],
    t: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> dict[str, Any]:
    """SABR implied-vol smile across strikes. CONCEPT:EE-034."""
    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}
    try:
        vols = [
            float(v)
            for v in engine.finance.sabr_smile(f, strikes, t, alpha, beta, rho, nu)
        ]
        return {"strikes": strikes, "vols": vols, "f": f, "t": t}
    except Exception as exc:  # noqa: BLE001
        logger.debug("sabr_smile failed: %s", exc)
        return {"error": str(exc)}


def calibrate(
    f: float,
    t: float,
    strikes: list[float],
    market_vols: list[float],
    beta: float = 0.5,
) -> dict[str, Any]:
    """Calibrate SABR (α, ρ, ν) to a market smile (β fixed). CONCEPT:EE-034.

    Returns ``{alpha, beta, rho, nu, rmse, converged}`` from the engine.
    """
    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}
    if len(strikes) != len(market_vols):
        return {"error": "strikes and market_vols must be the same length"}
    try:
        result = engine.finance.sabr_calibrate(f, t, strikes, market_vols, beta)
        return dict(result)
    except Exception as exc:  # noqa: BLE001
        logger.debug("sabr_calibrate failed: %s", exc)
        return {"error": str(exc)}


def vol_arb(
    f: float,
    t: float,
    strikes: list[float],
    market_vols: list[float],
    beta: float = 0.5,
) -> dict[str, Any]:
    """Vol-arb helper: calibrate SABR to the market smile, then compare each
    strike's *market* vol to the SABR-*fair* vol. CONCEPT:EE-034.

    Calibrating then re-pricing yields the smoothed, arbitrage-consistent fair
    smile; residuals (market − fair) flag strikes that look rich (positive
    residual → sell vol) or cheap (negative → buy vol). Decision-only: this
    returns a signal, never an order.

    Returns the calibration result plus per-strike
    ``{strike, market_vol, fair_vol, residual, signal}`` rows and the worst
    (largest |residual|) edge.
    """
    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}
    if len(strikes) != len(market_vols):
        return {"error": "strikes and market_vols must be the same length"}

    cal = calibrate(f, t, strikes, market_vols, beta)
    if "error" in cal:
        return cal

    fair = smile(f, strikes, t, cal["alpha"], cal["beta"], cal["rho"], cal["nu"])
    if "error" in fair:
        return fair

    rows: list[dict[str, Any]] = []
    for k, mv, fv in zip(strikes, market_vols, fair["vols"]):
        residual = mv - fv
        if residual > 0:
            signal = "rich_sell_vol"
        elif residual < 0:
            signal = "cheap_buy_vol"
        else:
            signal = "fair"
        rows.append(
            {
                "strike": k,
                "market_vol": mv,
                "fair_vol": fv,
                "residual": residual,
                "signal": signal,
            }
        )

    best = max(rows, key=lambda r: abs(r["residual"])) if rows else None
    return {
        "calibration": cal,
        "rows": rows,
        "best_edge": best,
        "f": f,
        "t": t,
        "beta": cal.get("beta", beta),
    }
