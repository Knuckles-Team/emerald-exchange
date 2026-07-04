"""emerald_signals ``insider_equilibrium`` action — CONCEPT:EX-AHE.harness.ee-32.

Captures the registered ``emerald_signals`` tool via a fake MCP and exercises the
new action end to end. Skips cleanly when the backing agent-utilities model
(``agent_utilities.domains.finance.insider_equilibrium``, KG-2.6) is not yet
installed in this env — the two repos merge independently.
"""

import importlib.util
import json

import pytest

from emerald_exchange.mcp.mcp_signals import register_signal_tools

_HAVE_MODEL = (
    importlib.util.find_spec("agent_utilities.domains.finance.insider_equilibrium")
    is not None
)


class _CaptureMCP:
    """Minimal MCP stand-in that captures ``@mcp.tool``-decorated callables."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):
        def _wrap(fn):
            self.tools[fn.__name__] = fn
            return fn

        return _wrap


def _signals_fn():
    mcp = _CaptureMCP()
    register_signal_tools(mcp)
    return mcp.tools["emerald_signals"]


@pytest.mark.skipif(not _HAVE_MODEL, reason="insider_equilibrium model not installed")
def test_insider_equilibrium_action_payload():
    fn = _signals_fn()
    params = {
        "sigma_v": 0.3,
        "sigma_u": 1.0,
        "enforcement": 0.7,
        "criminal_penalty": 0.05,
        "civil_penalty_rate": 1.0,
        "steps": 6,
    }
    out = json.loads(fn(action="insider_equilibrium", signals_json=json.dumps(params)))
    assert out["action"] == "insider_equilibrium"
    eq = out["equilibrium"]
    assert eq["intensity"] >= 0.0
    assert eq["kyle_lambda"] > 0.0
    assert eq["baseline_intensity"] > 0.0
    # schedule is sampled over the window and accelerates (non-decreasing in t).
    ints = [row["intensity"] for row in out["schedule"]]
    assert len(ints) == 7  # steps + 1
    assert ints == sorted(ints)
    assert "verdict" in out["policy"]


@pytest.mark.skipif(not _HAVE_MODEL, reason="insider_equilibrium model not installed")
def test_insider_equilibrium_rejects_bad_json():
    fn = _signals_fn()
    out = json.loads(fn(action="insider_equilibrium", signals_json="{not json"))
    assert "error" in out
