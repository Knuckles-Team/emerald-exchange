"""emerald_signals ``insider_equilibrium`` action — CONCEPT:EX-AHE.harness.ee-32.

The model runs in epistemic-graph (``FinanceSignalModels.insider_equilibrium``,
moved from agent-utilities by EH-423/AUD-30; the math and its reference values
are tested there). Here a fake engine proves the tool sends the model's
primitives with their defaults, maps the verdict to text, and refuses bad input
before calling the engine.
"""

import json

import pytest

import emerald_exchange._engine as eng
from emerald_exchange.mcp.mcp_signals import register_signal_tools


class _CaptureMCP:
    """Minimal MCP stand-in that captures ``@mcp.tool``-decorated callables."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):
        def _wrap(fn):
            self.tools[fn.__name__] = fn
            return fn

        return _wrap


class _InsiderEngine:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.finance = self

    def signal_models(self, op, request):
        self.requests.append({"op": op, **request})
        return {
            "equilibrium": {"intensity": 0.36, "binding_lever": "criminal"},
            "schedule": [{"t": 0.0, "intensity": 0.36}, {"t": 1.0, "intensity": 3.3}],
            "policy": {"verdict": "criminal_is_the_lever"},
        }


def _signals_fn():
    mcp = _CaptureMCP()
    register_signal_tools(mcp)
    return mcp.tools["emerald_signals"]


@pytest.fixture
def engine(monkeypatch):
    fake = _InsiderEngine()
    monkeypatch.setattr(eng, "finance_engine", lambda: fake)
    return fake


def test_insider_equilibrium_action_payload(engine):
    params = {
        "sigma_v": 0.3,
        "enforcement": 0.7,
        "criminal_penalty": 0.05,
        "civil_penalty_rate": 1.0,
        "ignored": 9,
        "steps": 6,
    }
    out = json.loads(
        _signals_fn()(action="insider_equilibrium", signals_json=json.dumps(params))
    )
    [sent] = engine.requests
    assert sent["op"] == "insider_equilibrium" and sent["steps"] == 6
    assert sent["inputs"] == {
        "sigma_v": 0.3,
        "sigma_u": 1.0,
        "enforcement": 0.7,
        "surveillance_kappa": 1.0,
        "criminal_penalty": 0.05,
        "civil_penalty_rate": 1.0,
        "horizon": 1.0,
    }
    assert out["action"] == "insider_equilibrium"
    assert out["equilibrium"]["binding_lever"] == "criminal"
    assert out["policy"]["verdict"] == "criminal_is_the_lever"
    assert "criminal sanctions" in out["policy"]["verdict_text"]


def test_insider_equilibrium_rejects_bad_json(engine):
    out = json.loads(
        _signals_fn()(action="insider_equilibrium", signals_json="{not json")
    )
    assert "error" in out
    assert engine.requests == []
