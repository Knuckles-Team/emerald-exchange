"""Tests for the stat-arb / dynamic-beta hedging + conviction-gate features.

CONCEPT:EX-AHE.harness.ee-28 / EE-030 / EE-031. Engine-backed assertions gate on the shared
``engine_client`` fixture (skipped cleanly with no socket) and additionally skip
when a version-behind daemon lacks the KG-2.20h/i kernels (``unknown variant``).
The import / wiring / offline-degradation assertions run unconditionally.
"""

import math

import pytest

from emerald_exchange.hedging import dynamic_beta_hedge
from emerald_exchange.market_making import (
    BookSnapshot,
    MMConfig,
    MarketMakingController,
    brier_score,
)
from emerald_exchange.risk_guards import RiskGuard, RiskLimits
from emerald_exchange.stat_arb import build_spread, ou_stat_arb_signal


def _skip_if_unknown_variant(res: dict) -> None:
    """Skip when a stale engine daemon lacks the kernel (mirrors no-socket skip)."""
    err = str(res.get("error", "")).lower()
    if "unknown variant" in err or "unknown method" in err:
        pytest.skip(f"engine lacks kernel (version behind): {res['error']}")


# ── pure / offline (no engine) ─────────────────────────────────────────


def test_build_spread_pairs_lengths():
    spread = build_spread([1.0, 2.0, 3.0], [0.5, 1.0, 1.5], hedge_ratio=2.0)
    assert spread == [0.0, 0.0, 0.0]


def test_dynamic_beta_input_validation():
    res = dynamic_beta_hedge([0.1, 0.2], [0.1])
    assert "error" in res and "same length" in res["error"]


def test_brier_score_input_validation():
    assert "error" in brier_score([0.5], [])
    assert "error" in brier_score([], [])


def test_empirical_kelly_offline_fallback():
    """With no engine + no history, empirical Kelly falls back to capped point Kelly."""
    rg = RiskGuard(RiskLimits(max_position_pct=0.02))
    f = rg.empirical_kelly_size(p=0.6, b=1.0, historical_returns=[], fraction=0.25)
    assert 0.0 <= f <= 0.02


def test_conviction_gate_blocks_on_disagreement():
    """The conviction gate is ON by default and blocks quotes without agreement."""
    cfg = MMConfig(bounded=True, conviction_min_agree=3)
    ctrl = MarketMakingController(cfg)
    book = BookSnapshot(
        ts=[0.0, 1.0],
        bid_px=[0.49, 0.50],
        bid_sz=[100.0, 100.0],
        ask_px=[0.51, 0.52],
        ask_sz=[100.0, 100.0],
    )
    # Only one strong vote → below min_agree=3 → must withdraw, no quotes posted.
    decision = ctrl.decide(book, inventory=0.0, signal_strengths=[0.9, 0.1, -0.05])
    assert decision.conviction_pass is False
    assert decision.withdraw is True
    assert decision.bid is None and decision.ask is None
    assert decision.reason == "conviction_gate_blocked"


def test_conviction_gate_open_without_signals():
    """No strengths supplied ⇒ gate vacuously open (prior behavior preserved)."""
    cfg = MMConfig(bounded=True)
    ctrl = MarketMakingController(cfg)
    book = BookSnapshot(
        ts=[0.0, 1.0],
        bid_px=[0.49, 0.50],
        bid_sz=[100.0, 100.0],
        ask_px=[0.51, 0.52],
        ask_sz=[100.0, 100.0],
    )
    decision = ctrl.decide(book, inventory=0.0)
    assert decision.conviction_pass is True
    assert decision.reason != "conviction_gate_blocked"


def test_conviction_gate_passes_on_agreement_local():
    """Enough agreeing strong votes ⇒ gate passes even via the local fallback."""
    cfg = MMConfig(bounded=True, conviction_min_agree=3)
    ctrl = MarketMakingController(cfg)
    book = BookSnapshot(
        ts=[0.0, 1.0],
        bid_px=[0.49, 0.50],
        bid_sz=[100.0, 100.0],
        ask_px=[0.51, 0.52],
        ask_sz=[100.0, 100.0],
    )
    decision = ctrl.decide(book, inventory=0.0, signal_strengths=[0.9, 0.8, 0.7, 0.65])
    assert decision.conviction_pass is True
    assert decision.reason != "conviction_gate_blocked"


# ── engine-backed ──────────────────────────────────────────────────────


def test_dynamic_beta_hedge_engine(engine_client):
    """Kalman-beta hedge returns a current beta + hedge ratio + band."""
    mkt = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.012] * 4
    ast = [0.012, -0.025, 0.02, 0.004, -0.013, 0.025, -0.006, 0.015] * 4
    res = dynamic_beta_hedge(ast, mkt)
    _skip_if_unknown_variant(res)
    assert "error" not in res
    assert "beta" in res and "hedge_ratio" in res
    assert math.isclose(res["hedge_ratio"], -res["beta"], rel_tol=1e-9)
    assert res["hedge_ratio_lower"] <= res["hedge_ratio"] <= res["hedge_ratio_upper"]


def test_ou_stat_arb_signal_engine(engine_client):
    """OU stat-arb pipeline emits a decision over a mean-reverting spread."""
    # venue A oscillates around venue B → stationary spread.
    px_b = [10.0 + 0.01 * i for i in range(80)]
    px_a = [px_b[i] + ((-1) ** i) * 0.2 for i in range(80)]
    res = ou_stat_arb_signal(px_a, px_b, hedge_ratio=1.0, dt=1.0)
    _skip_if_unknown_variant(res)
    assert "error" not in res
    assert res["signal"] in {
        "entry_long",
        "entry_short",
        "exit",
        "hold",
        "no_trade",
    }
    assert "current_spread" in res


def test_empirical_kelly_engine(engine_client):
    """Empirical Kelly sizing runs via the engine and respects the position cap."""
    rg = RiskGuard(RiskLimits(max_position_pct=0.05))
    hist = [1.0, -1.0, 1.0, 1.0, -1.0, 1.0] * 6
    res = rg.empirical_kelly_size(p=0.6, b=1.0, historical_returns=hist, fraction=0.5)
    assert 0.0 <= res <= 0.05


def test_brier_score_engine(engine_client):
    res = brier_score([0.9, 0.1, 0.8, 0.3, 0.6], [1, 0, 1, 0, 1])
    _skip_if_unknown_variant(res)
    assert "error" not in res
    assert "brier_score" in res and res["brier_score"] >= 0.0
