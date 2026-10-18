"""emerald's engine runs in epistemic-graph — CONCEPT:EX-AHE.harness.ee-20.

Every analysis in ``ontology/quant.ttl`` either binds a method epistemic-graph
serves or is refused. The bound methods and their parameters are checked
against the installed ``epistemic_graph`` client, the quoting policy is
checked against a recording engine, and the served analyses run on a real
engine started from ``epistemic-graph[server]``.
"""

import inspect
import json
from importlib.resources import files

import pytest
from agent_connector_sdk.compute import EngineCompute
from epistemic_graph.client import FinanceClient
from pyoxigraph import RdfFormat, Store

from emerald_exchange import _engine, analyses
from emerald_exchange.market_making import BookSnapshot, MarketMakingController, MMConfig
from emerald_exchange.risk_guards import RiskGuard, RiskLimits
from tests.test_insider_equilibrium_action import _Rdf

_VOCAB = _engine.QUANT_VOCABULARY

#: Analyses epistemic-graph does not serve yet; each has a handoff line.
REFUSED = {
    "EnsembleProbabilityAnalysis",
    "VolatilityArbitrageAnalysis",
    "EventBacktestAnalysis",
    "VenueFeeAnalysis",
    "DistributionShiftAnalysis",
    "SharpeRatioAnalysis",
    "HitRateAnalysis",
}


def _bindings() -> dict[str, str | None]:
    store = Store()
    ttl = files("emerald_exchange.ontology").joinpath("quant.ttl").read_bytes()
    store.load(ttl, format=RdfFormat.TURTLE)
    rows = store.query(
        "SELECT ?analysis ?method WHERE { ?analysis a <%sFinanceAnalysis> ; "
        "<%sappliesAlgorithm> ?algorithm . OPTIONAL { ?algorithm <%sservedBy> ?method } }"
        % (_VOCAB, _VOCAB, _VOCAB)
    )
    return {
        row["analysis"].value.removeprefix(_VOCAB): (
            None if row["method"] is None else row["method"].value
        )
        for row in rows
    }


def test_every_analysis_is_served_or_refused():
    bindings = _bindings()
    assert {name for name, method in bindings.items() if method is None} == REFUSED
    for name, method in bindings.items():
        if method is None:
            continue
        namespace, attr = method.split(".")
        assert namespace == "finance", name
        assert inspect.iscoroutinefunction(getattr(FinanceClient, attr)), name


# ── Recording engine for the quoting policy ───────────────────────────


class _Finance:
    def __init__(self, **overrides) -> None:
        self.calls: list[str] = []
        self._results = {
            "microprice_series": [0.5],
            "logit_quotes": {"bid": 0.48, "ask": 0.52, "reservation": 0.5, "half_spread": 0.02},
            "avellaneda_stoikov": {"bid": 99.0, "ask": 101.0},
            "vpin_pm": 0.0,
            "breakeven_alpha": 1.0,
            "surveillance_risk": {"legal_risk_score": 0.0, "informed_share": 0.0},
            "queue_imbalance": {"skew": [0.0], "bid_fill_time": [0.0], "ask_fill_time": [0.0]},
            "convergence_gate": {"pass": True},
            "ofi_series": [0.0],
            **overrides,
        }

    def __getattr__(self, name):
        if name.startswith("_") or name not in self._results:
            raise AttributeError(name)

        def call(**params):
            signature = inspect.signature(getattr(FinanceClient, name))
            signature.bind(None, **params)  # the served method accepts these
            self.calls.append(name)
            return self._results[name]

        return call


class _Client:
    def __init__(self, finance: _Finance) -> None:
        self.rdf = _Rdf()
        self.finance = finance


def _install(monkeypatch, **overrides) -> _Finance:
    finance = _Finance(**overrides)
    monkeypatch.setattr(_engine, "_COMPUTE_CACHE", EngineCompute(_Client(finance)))
    return finance


def _book(**extra) -> BookSnapshot:
    return BookSnapshot(
        ts=[0.0, 1.0],
        bid_px=[0.48, 0.49],
        bid_sz=[100.0, 120.0],
        ask_px=[0.52, 0.51],
        ask_sz=[100.0, 90.0],
        buy_vol=[10.0, 12.0],
        sell_vol=[8.0, 9.0],
        p_mean=[0.50, 0.50],
        **extra,
    )


def test_quotes_come_from_the_engine(monkeypatch):
    finance = _install(monkeypatch)
    d = MarketMakingController(MMConfig(bounded=True, tick=0.01)).decide(_book(), 0.0)
    assert (d.bid, d.ask, d.reason, d.engine_used) == (0.48, 0.52, "engine_quotes", True)
    assert {"microprice_series", "logit_quotes", "vpin_pm", "surveillance_risk"} <= set(
        finance.calls
    )


def test_unbounded_book_uses_avellaneda_stoikov(monkeypatch):
    finance = _install(monkeypatch, microprice_series=[100.0])
    book = BookSnapshot(bid_px=[99.0], bid_sz=[1.0], ask_px=[101.5], ask_sz=[1.0])
    d = MarketMakingController(MMConfig(bounded=False, tick=0.5, post_only=False)).decide(
        book, 0.0
    )
    assert "avellaneda_stoikov" in finance.calls
    assert (d.bid, d.ask) == (99.0, 101.0)


def test_conviction_gate_blocks_on_engine_verdict(monkeypatch):
    _install(monkeypatch, convergence_gate={"pass": False, "agree": 1})
    d = MarketMakingController(MMConfig()).decide(_book(), 0.0, signal_strengths=[0.9, 0.1])
    assert d.withdraw and d.reason == "conviction_gate_blocked"
    assert d.bid is None and d.ask is None


def test_legal_risk_gate_withdraws(monkeypatch):
    _install(monkeypatch, surveillance_risk={"legal_risk_score": 0.95, "informed_share": 1.8})
    d = MarketMakingController(MMConfig(legal_risk_max=0.85)).decide(_book(), 0.0)
    assert d.withdraw and d.reason == "legal_risk_withdraw"
    assert (d.legal_risk_score, d.informed_share) == (0.95, 1.8)


def test_toxicity_and_queue_gates(monkeypatch):
    _install(monkeypatch, vpin_pm=0.4, breakeven_alpha=0.1)
    d = MarketMakingController(MMConfig()).decide(_book(), 0.0)
    assert d.reason == "toxicity_withdraw"
    _install(
        monkeypatch,
        queue_imbalance={"skew": [0.2], "bid_fill_time": [3.0], "ask_fill_time": [1.0]},
    )
    d = MarketMakingController(MMConfig(queue_fill_time_max=1.0)).decide(_book(), 0.0)
    assert d.reason == "queue_adverse_selection" and d.queue_fill_time == 3.0


def test_venue_rules_tick_inventory_and_post_only(monkeypatch):
    _install(monkeypatch)
    d = MarketMakingController(MMConfig(max_inventory=10.0)).decide(_book(), 50.0)
    assert d.bid is None and d.ask == 0.52
    _install(monkeypatch, logit_quotes={"bid": 0.515, "ask": 0.53})
    d = MarketMakingController(MMConfig(tick=0.01)).decide(_book(), 0.0)
    assert d.bid is None  # would cross the 0.51 ask; post-only drops it


def test_no_engine_withdraws_without_local_fallback(monkeypatch):
    monkeypatch.setattr(_engine, "_COMPUTE_CACHE", None)
    d = MarketMakingController(MMConfig()).decide(_book(), 0.0)
    assert d.withdraw and d.reason == _engine.ENGINE_REQUIRED_ERR
    assert d.bid is None and d.ask is None


def test_kelly_sizing_requires_the_engine(monkeypatch):
    from agent_connector_sdk.compute import ComputeUnavailableError

    monkeypatch.setattr(_engine, "_COMPUTE_CACHE", None)
    with pytest.raises(ComputeUnavailableError):
        RiskGuard().bayesian_kelly_size(wins=60, losses=40, cost=0.4)


@pytest.mark.parametrize(
    ("call", "analysis"),
    [
        (lambda: analyses.venue_fee(0.5, 10.0, "finance", is_maker=True), "VenueFeeAnalysis"),
        (lambda: analyses.event_backtest([]), "EventBacktestAnalysis"),
        (lambda: analyses.distribution_shift([0.0], [0.0]), "DistributionShiftAnalysis"),
        (lambda: analyses.hit_rate([0.1, -0.1]), "HitRateAnalysis"),
    ],
)
def test_unserved_analyses_are_refused(monkeypatch, call, analysis):
    _install(monkeypatch)
    out = call()
    assert out["error"] == "not_served"
    assert out["method"] == _engine.analysis_iri(analysis)
    assert out["handoff"] == _engine.HANDOFF_OWNER


# ── Live engine ───────────────────────────────────────────────────────


def test_live_quote(live_engine):
    d = MarketMakingController(MMConfig(bounded=True, tick=0.01)).decide(
        _book(bid_q=[100.0, 120.0], ask_q=[100.0, 90.0]), 0.0
    )
    assert d.engine_used and d.reason != _engine.ENGINE_REQUIRED_ERR
    assert 0.0 < d.fair_value < 1.0
    if not d.withdraw:
        assert d.bid is None or 0.0 < d.bid < 1.0


def test_live_hedge_beta(live_engine):
    market = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, 0.0, 0.01]
    asset = [1.5 * r for r in market]
    out = analyses.dynamic_beta_hedge(asset, market)
    assert len(out["states"]) == len(market)
    assert out["beta"] > 1.0


def test_live_stat_arb(live_engine):
    spread = [0.1 * ((-1) ** i) + 0.01 * (i % 3) for i in range(60)]
    out = analyses.ou_stat_arb_signal(spread)
    assert {"theta", "mu", "sigma", "sigma_eq"} <= set(out["ou"])
    assert {"entry_long", "entry_short", "exit"} <= set(out["thresholds"])
    assert "stationary_5pct" in out["adf"]


def test_live_validation_kelly_and_brier(live_engine):
    returns = [0.1, -0.05, 0.2, 0.0, 0.15, -0.1, 0.05, 0.08]
    out = analyses.validate_returns(returns, n_trials=3, observed_sharpe=0.5)
    assert isinstance(out["deflated_sharpe"], float)
    assert out["cpcv_splits"] and "max_drawdown" in out["performance"]
    assert analyses.validate_returns(returns)["deflated_sharpe"]["error"] == "not_served"
    assert isinstance(analyses.probability_overfit([[0.1, 0.2]], [[0.05, 0.1]])["pbo"], float)
    assert 0.0 <= analyses.brier_score([0.9, 0.2], [1.0, 0.0])["brier_score"] < 0.25
    guard = RiskGuard(RiskLimits(max_position_pct=0.02))
    assert 0.0 <= guard.bayesian_kelly_size(wins=60, losses=40, cost=0.4) <= 0.02
    f = guard.empirical_kelly_size(0.6, 1.0, returns, n_simulations=500)
    assert 0.0 <= f <= 0.02


def test_live_market_making_tool(live_engine):
    from emerald_exchange.mcp.mcp_market_making import register_market_making_tools
    from tests.test_insider_equilibrium_action import _CaptureMCP

    mcp = _CaptureMCP()
    register_market_making_tools(mcp)
    fn = mcp.tools["emerald_market_making"]
    year = {key: 100.0 for key in analyses.STANDARD_LINE_ITEMS}
    forensic = json.loads(fn("forensic", json.dumps({"this_year": year, "prior_year": year})))
    assert "verdict" in forensic
    assert json.loads(fn("fee", "{}"))["error"] == "not_served"
