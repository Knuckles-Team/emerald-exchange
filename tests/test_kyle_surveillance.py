"""Kyle insider/stealth surveillance gate — CONCEPT:EX-AHE.harness.sustained-adverse-selection.

Live-path tests: exercise ``MarketMakingController.decide`` and
``RiskGuard.evaluate_graduation`` and assert the surveillance score is computed,
surfaced, and acted on per the operator threshold. The engine is faked so only
``surveillance_risk`` is implemented — every other engine call degrades through
the controller's existing local-fallback paths.
"""

import emerald_exchange.market_making as mm
from emerald_exchange.market_making import (
    BookSnapshot,
    MarketMakingController,
    MMConfig,
)
from emerald_exchange.risk_guards import RiskGuard, RiskLimits


def _book() -> BookSnapshot:
    return BookSnapshot(
        ts=[0.0, 0.5, 1.0],
        bid_px=[0.49, 0.49, 0.50],
        bid_sz=[100.0, 100.0, 100.0],
        ask_px=[0.51, 0.51, 0.51],
        ask_sz=[100.0, 100.0, 100.0],
        buy_vol=[500.0, 500.0, 500.0],
        sell_vol=[5.0, 5.0, 5.0],
        p_mean=[0.5, 0.5, 0.5],
    )


class _FakeFinance:
    def __init__(self, scores: dict) -> None:
        self._scores = scores

    def surveillance_risk(self, *args, **kwargs) -> dict:
        return self._scores


class _FakeEngine:
    def __init__(self, scores: dict) -> None:
        self.finance = _FakeFinance(scores)


_HIGH = {"legal_risk_score": 0.95, "informed_share": 1.8}


def test_legal_risk_gate_withdraws_when_threshold_tripped(monkeypatch):
    monkeypatch.setattr(mm, "finance_engine", lambda: _FakeEngine(_HIGH))
    ctrl = MarketMakingController(
        MMConfig(bounded=True, tick=0.01, legal_risk_max=0.85)
    )
    d = ctrl.decide(_book(), inventory=0.0)
    assert d.withdraw
    assert d.reason == "legal_risk_withdraw"
    assert d.legal_risk_score == 0.95
    assert d.informed_share == 1.8


def test_legal_risk_score_surfaced_but_default_does_not_act(monkeypatch):
    # Default legal_risk_max=1.0 ⇒ a score below 1.0 never trips (behavior-safe),
    # but the score is still computed and surfaced for observability.
    monkeypatch.setattr(mm, "finance_engine", lambda: _FakeEngine(_HIGH))
    ctrl = MarketMakingController(MMConfig(bounded=True, tick=0.01))
    d = ctrl.decide(_book(), inventory=0.0)
    assert d.legal_risk_score == 0.95
    assert d.reason != "legal_risk_withdraw"


def test_legal_risk_degrades_cleanly_without_engine(monkeypatch):
    monkeypatch.setattr(mm, "finance_engine", lambda: None)
    ctrl = MarketMakingController(
        MMConfig(bounded=True, tick=0.01, legal_risk_max=0.5)
    )
    d = ctrl.decide(_book(), inventory=0.0)
    assert d.legal_risk_score == 0.0
    assert d.reason != "legal_risk_withdraw"


def test_graduation_blocked_by_legal_risk():
    guard = RiskGuard(RiskLimits(stage="paper"))
    policy = {"graduation": {"paper_to_advisory": {"max_legal_risk": 0.8}}}
    metrics = {
        "paper_trades": 0,
        "deflated_sharpe": 0.0,
        "pbo": 0.0,
        "hit_rate": 1.0,
        "legal_risk_score": 0.95,
    }
    out = guard.evaluate_graduation(metrics, policy)
    assert "max_legal_risk" in out["unmet"]
    assert out["eligible"] is False
