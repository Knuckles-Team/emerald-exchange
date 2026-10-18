"""evaluate_event_arbitrage is refused until epistemic-graph serves it."""

import asyncio
import json

from agent_connector_sdk.compute import EngineCompute

from emerald_exchange import _engine
from emerald_exchange.mcp.mcp_prediction_markets import register_prediction_market_tools
from tests.test_insider_equilibrium_action import _CaptureMCP, _Client


def test_unserved_ensemble_probability_is_refused(monkeypatch):
    monkeypatch.setattr(_engine, "_COMPUTE_CACHE", EngineCompute(_Client()))
    mcp = _CaptureMCP()
    register_prediction_market_tools(mcp)
    (tool,) = [fn for name, fn in mcp.tools.items() if "prediction" in name]
    out = json.loads(
        asyncio.run(
            tool(action="evaluate_event_arbitrage", params_json='{"condition_met_count": 20}')
        )
    )
    assert out["error"] == "not_served"
    assert out["method"].endswith("#EnsembleProbabilityAnalysis")
