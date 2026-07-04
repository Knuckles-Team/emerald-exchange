"""Ornstein-Uhlenbeck Statistical-Arbitrage Signal — CONCEPT:EX-AHE.harness.ee-29.

A thin controller over the Rust ``epistemic-graph`` engine's stat-arb kernels
(KG-2.20h): build the spread between two venues' price series for the *same*
outcome, gate on stationarity with the Augmented Dickey-Fuller test
(``client.finance.adf_test``), then calibrate an Ornstein-Uhlenbeck process
(``ou_calibrate``) and derive optimal entry/exit thresholds
(``ou_optimal_thresholds``). Finally it compares the *current* spread to those
thresholds and emits an entry/exit signal.

emerald-exchange owns no stat-arb math — all compute is delegated to the engine.
Importing this module never requires a running engine; when the engine is
unreachable (or a stale daemon lacks the kernel) the call degrades cleanly to an
``{"error": ...}`` payload. The signal is a *decision* only — it never places an
order; live execution stays gated behind ``RiskGuard.require_human_approval_live``.
"""

from __future__ import annotations

import logging
from typing import Any

from emerald_exchange._engine import ENGINE_REQUIRED_ERR, finance_engine

logger = logging.getLogger(__name__)


def build_spread(
    px_a: list[float], px_b: list[float], hedge_ratio: float = 1.0
) -> list[float]:
    """Construct the venue-A − hedge_ratio·venue-B price spread (paired length)."""
    n = min(len(px_a), len(px_b))
    return [float(px_a[i]) - hedge_ratio * float(px_b[i]) for i in range(n)]


def ou_stat_arb_signal(
    px_a: list[float],
    px_b: list[float],
    hedge_ratio: float = 1.0,
    dt: float = 1.0,
    adf_max_lag: int = 1,
    cost: float = 0.0,
    require_stationary: bool = True,
) -> dict[str, Any]:
    """Build a spread, ADF-gate it, OU-calibrate, and emit an entry/exit signal.

    CONCEPT:EX-AHE.harness.ee-29. Pipeline:

    1. ``spread = px_a − hedge_ratio·px_b`` (same-outcome cross-venue pair).
    2. ``adf_test`` — if ``require_stationary`` and not ``stationary_5pct``, return
       a no-trade signal (the pair is not mean-reverting enough to trade).
    3. ``ou_calibrate`` → ``{theta, mu, sigma, half_life, sigma_eq}``.
    4. ``ou_optimal_thresholds`` → entry/exit bands.
    5. Compare the *current* spread vs the bands → entry_long / entry_short /
       exit / hold.

    Returns a decision dict (never an order); or ``{"error": ...}`` when the
    engine is unreachable / the kernel is missing / the inputs are invalid.
    """
    if min(len(px_a), len(px_b)) < 10:
        return {"error": "need at least 10 paired price observations"}

    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}

    spread = build_spread(px_a, px_b, hedge_ratio)
    current = spread[-1]

    try:
        adf = engine.finance.adf_test(spread, adf_max_lag)
    except Exception as exc:  # noqa: BLE001 — degrade cleanly (incl. stale daemon)
        logger.debug("adf_test failed: %s", exc)
        return {"error": str(exc)}

    stationary = (
        bool(adf.get("stationary_5pct", False)) if isinstance(adf, dict) else False
    )
    if require_stationary and not stationary:
        return {
            "signal": "no_trade",
            "reason": "spread_not_stationary",
            "stationary_5pct": stationary,
            "adf": adf,
            "current_spread": current,
            "engine_used": True,
        }

    try:
        ou = engine.finance.ou_calibrate(spread, dt)
        thresholds = engine.finance.ou_optimal_thresholds(
            float(ou["theta"]),
            float(ou["mu"]),
            float(ou["sigma"]),
            float(ou["sigma_eq"]),
            cost,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("OU calibration/thresholds failed: %s", exc)
        return {"error": str(exc)}

    mu = float(ou["mu"])
    entry_long = float(thresholds["entry_long"])
    entry_short = float(thresholds["entry_short"])
    exit_band = float(thresholds["exit"])

    # Thresholds are expressed as spread *levels* around mu. A spread far below
    # entry_long ⇒ buy the spread (long A / short B); far above entry_short ⇒
    # sell the spread; inside the exit band ⇒ flatten; else hold.
    if current <= entry_long:
        signal, reason = "entry_long", "spread_below_entry_long"
    elif current >= entry_short:
        signal, reason = "entry_short", "spread_above_entry_short"
    elif abs(current - mu) <= abs(exit_band - mu):
        signal, reason = "exit", "spread_within_exit_band"
    else:
        signal, reason = "hold", "between_entry_and_exit"

    return {
        "signal": signal,
        "reason": reason,
        "current_spread": current,
        "stationary_5pct": stationary,
        "hedge_ratio": hedge_ratio,
        "ou": ou,
        "thresholds": thresholds,
        "adf": adf,
        "engine_used": True,
    }
