"""Finance analyses run by epistemic-graph — CONCEPT:EX-AHE.harness.ee-20.

emerald-exchange holds no finance computation. Each function names one
analysis declared in ``ontology/quant.ttl``; epistemic-graph selects the
algorithm bound to it by SPARQL and runs the served method through
:mod:`agent_connector_sdk.compute` (see :func:`emerald_exchange._engine.run_analysis`).
An analysis without a served algorithm is refused with ``MethodNotServedError``;
there is no local fallback.

Every function returns a JSON-ready dict. An unreachable engine returns
``{"error": ENGINE_REQUIRED_ERR}``; an unserved analysis returns
``{"error": "not_served", "method": ..., "handoff": ...}``. Results are
decisions or measurements only; none places an order.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from agent_connector_sdk.compute import ComputeUnavailableError, MethodNotServedError

from emerald_exchange._engine import engine_error, refuse, run_analysis

#: The 17 standardized line items of the engine's ``forensic_report`` year
#: schema (emitted by ``data/edgar.standardize_financials``).
STANDARD_LINE_ITEMS = (
    "sales",
    "cogs",
    "sga",
    "net_income",
    "cfo",
    "receivables",
    "current_assets",
    "current_liabilities",
    "ppe_net",
    "depreciation",
    "total_assets",
    "total_liabilities",
    "long_term_debt",
    "retained_earnings",
    "ebit",
    "market_cap",
    "shares",
)


def _served(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Map an unavailable engine or unserved analysis to its tool payload."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except (ComputeUnavailableError, MethodNotServedError) as exc:
            return engine_error(exc)

    return wrapper


def standardize_year(raw: dict[str, Any]) -> dict[str, float]:
    """Shape a raw financials dict into the engine's year schema (missing = 0)."""
    out: dict[str, float] = {}
    for key in STANDARD_LINE_ITEMS:
        try:
            out[key] = float(raw.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            out[key] = 0.0
    return out


# ── Forensic accounting ───────────────────────────────────────────────


@_served
def forensic_screen(
    this_year: dict[str, Any], prior_year: dict[str, Any]
) -> dict[str, Any]:
    """Beneish / Altman / Piotroski / Sloan two-year report (ForensicAccountingAnalysis)."""
    report = run_analysis(
        "ForensicAccountingAnalysis",
        this_year=standardize_year(this_year),
        prior_year=standardize_year(prior_year),
    )
    return dict(report) if isinstance(report, dict) else {"report": report}


# ── Hedging and statistical arbitrage ─────────────────────────────────


@_served
def dynamic_beta_hedge(
    asset_returns: list[float],
    market_returns: list[float],
    q: float = 1e-5,
    r: float = 1e-3,
    beta0: float = 1.0,
    p0: float = 1.0,
) -> dict[str, Any]:
    """Time-varying hedge beta by Kalman filter (HedgeBetaAnalysis).

    Returns the engine's ``{states, variances}`` with the current (last) beta.
    """
    if len(asset_returns) != len(market_returns):
        return {"error": "asset_returns and market_returns must be the same length"}
    out = run_analysis(
        "HedgeBetaAnalysis",
        market_returns=market_returns,
        asset_returns=asset_returns,
        q=q,
        r=r,
        beta0=beta0,
        p0=p0,
    )
    states = list(out.get("states") or [])
    variances = list(out.get("variances") or [])
    return {
        "beta": states[-1] if states else None,
        "beta_variance": variances[-1] if variances else None,
        "states": states,
        "variances": variances,
        "n_obs": len(asset_returns),
    }


@_served
def ou_stat_arb_signal(
    spread: list[float], dt: float = 1.0, adf_max_lag: int = 1, cost: float = 0.0
) -> dict[str, Any]:
    """Stationarity, OU calibration and optimal bands for a spread.

    Runs SpreadStationarityAnalysis, MeanReversionCalibrationAnalysis and
    MeanReversionThresholdAnalysis; the connector compares nothing itself.
    """
    adf = run_analysis("SpreadStationarityAnalysis", series=spread, max_lag=adf_max_lag)
    ou = run_analysis("MeanReversionCalibrationAnalysis", spread=spread, dt=dt)
    thresholds = run_analysis(
        "MeanReversionThresholdAnalysis",
        theta=float(ou["theta"]),
        mu=float(ou["mu"]),
        sigma=float(ou["sigma"]),
        sigma_eq=float(ou["sigma_eq"]),
        cost=cost,
    )
    return {"adf": adf, "ou": ou, "thresholds": thresholds}


# ── Derivatives (SABR) ────────────────────────────────────────────────


@_served
def implied_vol(
    f: float, k: float, t: float, alpha: float, beta: float, rho: float, nu: float
) -> dict[str, Any]:
    """SABR implied vol for one strike (ImpliedVolatilityAnalysis)."""
    vol = run_analysis(
        "ImpliedVolatilityAnalysis",
        f=f,
        k=k,
        t=t,
        alpha=alpha,
        beta=beta,
        rho=rho,
        nu=nu,
    )
    return {"implied_vol": vol, "f": f, "k": k, "t": t}


@_served
def smile(
    f: float,
    strikes: list[float],
    t: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> dict[str, Any]:
    """SABR implied-vol smile across strikes (VolatilitySmileAnalysis)."""
    vols = run_analysis(
        "VolatilitySmileAnalysis",
        f=f,
        strikes=strikes,
        t=t,
        alpha=alpha,
        beta=beta,
        rho=rho,
        nu=nu,
    )
    return {"strikes": strikes, "vols": list(vols), "f": f, "t": t}


@_served
def calibrate(
    f: float,
    t: float,
    strikes: list[float],
    market_vols: list[float],
    beta: float = 0.5,
) -> dict[str, Any]:
    """Calibrate SABR to a market smile (VolatilityCalibrationAnalysis)."""
    if len(strikes) != len(market_vols):
        return {"error": "strikes and market_vols must be the same length"}
    return dict(
        run_analysis(
            "VolatilityCalibrationAnalysis",
            f=f,
            t=t,
            strikes=strikes,
            market_vols=market_vols,
            beta=beta,
        )
    )


@_served
def vol_arb(
    f: float,
    t: float,
    strikes: list[float],
    market_vols: list[float],
    beta: float = 0.5,
) -> dict[str, Any]:
    """Rich/cheap strike classification against the SABR-fair smile.

    Refused: epistemic-graph serves calibration and the smile but not the
    residual classification (VolatilityArbitrageAnalysis).
    """
    refuse("VolatilityArbitrageAnalysis")


# ── Market microstructure ─────────────────────────────────────────────


@_served
def brier_score(forecasts: list[float], outcomes: list[float]) -> dict[str, Any]:
    """Brier calibration score of forecasts (ForecastCalibrationAnalysis)."""
    if len(forecasts) != len(outcomes) or not forecasts:
        return {"error": "forecasts and outcomes must be non-empty and the same length"}
    score = run_analysis(
        "ForecastCalibrationAnalysis", forecasts=forecasts, outcomes=outcomes
    )
    return {"brier_score": score, "n": len(forecasts)}


# ── Backtest validation ───────────────────────────────────────────────


def _attempt(name: str, /, **params: Any) -> Any:
    """Run one analysis, or return its refusal payload in place of the value."""
    try:
        return run_analysis(name, **params)
    except MethodNotServedError as exc:
        return engine_error(exc)


@_served
def validate_returns(
    returns: list[float],
    n_trials: int = 1,
    cpcv_groups: int = 6,
    cpcv_test_groups: int = 2,
    observed_sharpe: float | None = None,
) -> dict[str, Any]:
    """Performance, deflated Sharpe and purged CPCV splits of backtest returns.

    epistemic-graph does not serve an observed Sharpe ratio yet
    (SharpeRatioAnalysis, refused): pass ``observed_sharpe`` to get the
    deflated Sharpe, otherwise that entry carries the refusal.
    """
    if len(returns) < 2:
        return {"error": "need >= 2 returns to validate"}
    observed = (
        _attempt("SharpeRatioAnalysis", returns=returns)
        if observed_sharpe is None
        else float(observed_sharpe)
    )
    deflated = (
        run_analysis(
            "DeflatedSharpeAnalysis",
            observed_sr=observed,
            n_trials=n_trials,
            sr_returns=returns,
        )
        if isinstance(observed, float)
        else observed
    )
    return {
        "performance": run_analysis("PerformanceAnalysis", returns=returns),
        "observed_sharpe": observed,
        "deflated_sharpe": deflated,
        "cpcv_splits": run_analysis(
            "CrossValidationSplitAnalysis",
            n_samples=len(returns),
            n_groups=cpcv_groups,
            n_test_groups=cpcv_test_groups,
        ),
        "n_returns": len(returns),
    }


@_served
def hit_rate(returns: list[float]) -> dict[str, Any]:
    """Share of positive returns (HitRateAnalysis, refused)."""
    return {"hit_rate": run_analysis("HitRateAnalysis", returns=returns)}


@_served
def probability_overfit(
    insample: list[list[float]], oos: list[list[float]]
) -> dict[str, Any]:
    """Probability of backtest overfit across strategies (BacktestOverfitAnalysis)."""
    return {"pbo": run_analysis("BacktestOverfitAnalysis", insample=insample, oos=oos)}


@_served
def event_backtest(events: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
    """Event-driven L2-queue backtest with maker/taker fees.

    Refused until epistemic-graph serves EventBacktestAnalysis.
    """
    refuse("EventBacktestAnalysis")


# ── Fees and distribution shift ───────────────────────────────────────


@_served
def venue_fee(
    price: float, size: float, category: str, *, is_maker: bool
) -> dict[str, Any]:
    """Venue taker fee / maker rebate for a fill (VenueFeeAnalysis, refused)."""
    refuse("VenueFeeAnalysis")


@_served
def distribution_shift(
    historical: list[float], recent: list[float], threshold: float = 0.1
) -> dict[str, Any]:
    """Two-sample regime-shift test (DistributionShiftAnalysis, refused)."""
    refuse("DistributionShiftAnalysis")
