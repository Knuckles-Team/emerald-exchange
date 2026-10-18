"""emerald_signals runs its analyses in epistemic-graph — CONCEPT:EX-AHE.harness.ee-32.

The algorithm for each analysis is selected by SPARQL over the connector's own
``ontology/quant.ttl`` (loaded into an in-process RDF store standing in for the
graph service) and run through the SDK compute adapter. The fake finance
namespace records the served call; the connector computes nothing itself.
"""

import json
from importlib.resources import files

import pytest
from agent_connector_sdk.compute import EngineCompute
from pyoxigraph import RdfFormat, Store

from emerald_exchange import _engine
from emerald_exchange.mcp.mcp_signals import register_signal_tools


class _CaptureMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):
        def _wrap(fn):
            self.tools[fn.__name__] = fn
            return fn

        return _wrap


class _Rdf:
    def __init__(self) -> None:
        self.store = Store()
        ttl = files("emerald_exchange.ontology").joinpath("quant.ttl").read_bytes()
        self.store.load(ttl, format=RdfFormat.TURTLE)

    def sparql(self, *, query: str):
        rows = []
        for solution in self.store.query(query):
            rows.append(
                {
                    name: (None if solution[name] is None else solution[name].value)
                    for name in ("algorithm", "method", "op")
                }
            )
        return rows


class _Finance:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def signal_models(self, **params):
        self.calls.append(("signal_models", params))
        if params["op"] == "insider_equilibrium":
            steps = params["request"]["steps"]
            return {
                "equilibrium": {"intensity": 0.4, "kyle_lambda": 0.15},
                "schedule": [{"t": i / steps, "intensity": 0.4} for i in range(steps + 1)],
                "policy": {"verdict": "criminal_is_the_lever"},
            }
        return {"posterior_up": 0.66, "seeded": 0, "sources": [{"name": "rsi"}]}

    def detect_regimes(self, **params):
        self.calls.append(("detect_regimes", params))
        return {"states": [0, 1], "means": [0.0, 0.01]}


class _Nodes:
    def list(self):
        return []


class _Client:
    def __init__(self) -> None:
        self.rdf = _Rdf()
        self.finance = _Finance()
        self.nodes = _Nodes()


@pytest.fixture
def client(monkeypatch):
    fake = _Client()
    monkeypatch.setattr(_engine, "_COMPUTE_CACHE", EngineCompute(fake))
    return fake


def _signals_fn():
    mcp = _CaptureMCP()
    register_signal_tools(mcp)
    return mcp.tools["emerald_signals"]


def test_insider_equilibrium_is_selected_and_run_by_the_engine(client):
    params = {"sigma_v": 0.3, "enforcement": 0.7, "criminal_penalty": 0.05, "steps": 6}
    out = json.loads(
        _signals_fn()(action="insider_equilibrium", signals_json=json.dumps(params))
    )
    assert out["action"] == "insider_equilibrium"
    assert len(out["schedule"]) == 7
    name, call = client.finance.calls[0]
    assert (name, call["op"]) == ("signal_models", "insider_equilibrium")
    assert call["request"]["inputs"]["enforcement"] == 0.7
    assert call["request"]["inputs"]["sigma_u"] == 1.0
    assert call["request"]["steps"] == 6


def test_fuse_runs_bayes_fusion_in_the_engine(client):
    out = json.loads(_signals_fn()(action="fuse", signals_json='{"rsi": 1}'))
    assert out["posterior_up"] == 0.66
    name, call = client.finance.calls[0]
    assert call["op"] == "bayes_fuse"
    assert call["request"]["directions"] == {"rsi": 1}


def test_regime_runs_the_engine_hmm(client):
    prices = {"close_prices": [100, 101, 99, 102, 103]}
    out = json.loads(_signals_fn()(action="regime", signals_json=json.dumps(prices)))
    assert out["regimes"]["states"] == [0, 1]
    name, call = client.finance.calls[0]
    assert name == "detect_regimes" and len(call["observations"]) == 4


def test_insider_equilibrium_rejects_bad_json(client):
    out = json.loads(_signals_fn()(action="insider_equilibrium", signals_json="{not json"))
    assert "error" in out


def test_unreachable_engine_reports_requirement(monkeypatch):
    monkeypatch.setattr(_engine, "_COMPUTE_CACHE", None)
    out = json.loads(_signals_fn()(action="fuse", signals_json='{"rsi": 1}'))
    assert out["error"] == _engine.ENGINE_REQUIRED_ERR
