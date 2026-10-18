"""Tests for the HFT suite — execution policy, ws client, signal and strategy
tools. CONCEPT:EX-AHE.harness.ee-21..026

Finance analyses run in epistemic-graph; the engine-backed checks use the live
engine (``live_engine``), started from ``epistemic-graph[server]``.
"""

import json

from emerald_exchange._engine import ENGINE_REQUIRED_ERR

from emerald_exchange.risk_guards import RiskGuard, RiskLimits


def test_emerald_signals_fuse_requires_engine(monkeypatch):
    """Fusion runs in epistemic-graph; without an engine the tool says so and
    computes nothing locally."""
    import emerald_exchange._engine as eng
    import emerald_exchange.mcp.mcp_signals as ms

    monkeypatch.setattr(eng, "_COMPUTE_CACHE", None)

    captured = {}

    class _MCP:
        def tool(self, *a, **k):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

    ms.register_signal_tools(_MCP())
    out = json.loads(
        captured["emerald_signals"](
            action="fuse", signals_json='{"ofi": 1, "queue": 1}'
        )
    )
    assert out == {"error": eng.ENGINE_REQUIRED_ERR}


def test_emerald_strategy_backtest_reports_refusals(live_engine):
    """CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion — backtest computes priors and writes them to the KG.
    Skips cleanly when the engine binary lacks the finance kernels."""
    import emerald_exchange.mcp.mcp_strategy as mst

    captured = {}

    class _MCP:
        def tool(self, *a, **k):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

    mst.register_strategy_tools(_MCP())
    out = json.loads(
        captured["emerald_strategy"](
            action="backtest",
            strategy_id="sig:test_ofi",
            returns_json=json.dumps([0.01, -0.004, 0.02, 0.015, -0.002, 0.011]),
            name="ofi",
        )
    )
    assert out["hit_rate"]["error"] == "not_served"
    assert out["deflated_sharpe"]["error"] == "not_served"
    assert isinstance(out["pbo"], float)
    assert out["priors_written"] is False


def test_require_human_approval_live_preserved():
    """Live execution gating must NOT be weakened by the new sizing path."""
    guard = RiskGuard(RiskLimits(require_human_approval_live=True))
    check = guard.pre_trade_check("X", 1, 0.5, 1000, 1000, is_live=True)
    assert not check.approved
    assert "human approval" in check.reason.lower()


def test_paper_stage_blocks_live():
    """CONCEPT:EX-AHE.harness.bounded-autonomous-allows-small — paper stage refuses live orders; paper orders pass."""
    from emerald_exchange.risk_guards import load_execution_policy

    policy = load_execution_policy()
    assert policy["stage"] == "paper"  # ships paper-first
    guard = RiskGuard(RiskLimits.from_execution_policy(policy))
    live = guard.pre_trade_check("X", 1, 0.5, 1000, 1000, is_live=True)
    assert not live.approved and "human approval" in live.reason.lower()
    paper = guard.pre_trade_check("X", 1, 0.5, 1000, 1000, is_live=False)
    assert paper.approved


def test_bounded_autonomous_caps():
    """CONCEPT:EX-AHE.harness.bounded-autonomous-allows-small — bounded_autonomous allows small live orders, blocks large."""
    limits = RiskLimits.from_execution_policy(
        {
            "stage": "bounded_autonomous",
            "bounded_autonomous": {
                "max_notional_per_trade": 500,
                "require_human_above": 1000,
            },
        }
    )
    assert limits.require_human_approval_live is False
    guard = RiskGuard(limits)
    # within caps (notional 400) on a big book ⇒ allowed
    ok = guard.pre_trade_check("X", 800, 0.5, 1_000_000, 1_000_000, is_live=True)
    assert ok.approved
    # above require_human_above (notional 1200) ⇒ blocked
    big = guard.pre_trade_check("X", 2400, 0.5, 1_000_000, 1_000_000, is_live=True)
    assert not big.approved and "human approval" in big.reason.lower()


def test_graduation_is_eligibility_only_and_stage_is_human_gated(monkeypatch):
    """CONCEPT:EX-AHE.harness.bounded-autonomous-allows-small — evaluate_graduation never changes stage; approve_stage
    requires the human token."""
    guard = RiskGuard(RiskLimits(stage="paper"))
    policy = {
        "graduation": {
            "paper_to_advisory": {
                "min_paper_trades": 200,
                "min_deflated_sharpe": 1.0,
                "max_pbo": 0.3,
                "min_hit_rate": 0.52,
            }
        }
    }
    not_ready = guard.evaluate_graduation({"paper_trades": 10}, policy)
    assert not_ready["eligible"] is False and guard.limits.stage == "paper"
    ready = guard.evaluate_graduation(
        {"paper_trades": 300, "deflated_sharpe": 1.5, "pbo": 0.2, "hit_rate": 0.55},
        policy,
    )
    assert ready["eligible"] is True and guard.limits.stage == "paper"  # unchanged

    # Agent (no token) cannot promote; human with token can.
    assert guard.approve_stage("advisory", "guess") is False
    assert guard.limits.stage == "paper"
    monkeypatch.setenv("EMERALD_STAGE_APPROVAL_TOKEN", "s3cret")
    assert guard.approve_stage("advisory", "s3cret") is True
    assert guard.limits.stage == "advisory"


# ── WS client import-safety + gap logic (no live socket) ───────────────
def test_ws_client_imports_without_websockets():
    from emerald_exchange.ws_client import PolymarketMarketStream, WSConfig

    async def _noop(_msg):
        return None

    stream = PolymarketMarketStream(WSConfig(asset_ids=["a"]), on_message=_noop)
    assert stream.connected is False


def test_ws_sequence_gap_triggers_resync():
    import asyncio

    from emerald_exchange.ws_client import PolymarketMarketStream, WSConfig

    resyncs = []

    async def _msg(_m):
        return None

    async def _resync(asset, last, got):
        resyncs.append((asset, last, got))

    stream = PolymarketMarketStream(
        WSConfig(asset_ids=["a"]), on_message=_msg, on_resync=_resync
    )

    async def _drive():
        await stream._check_gap({"asset_id": "a", "seq": 1})
        await stream._check_gap({"asset_id": "a", "seq": 2})
        await stream._check_gap({"asset_id": "a", "seq": 5})  # gap 2 -> 5

    asyncio.run(_drive())
    assert resyncs == [("a", 2, 5)]


# ── MCP tool registration smoke ────────────────────────────────────────
def test_market_making_tool_registers_and_runs():
    from emerald_exchange.mcp.mcp_market_making import register_market_making_tools

    captured = {}

    class FakeMCP:
        def tool(self, *a, **k):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

    register_market_making_tools(FakeMCP())
    assert "emerald_market_making" in captured
    fn = captured["emerald_market_making"]

    out = json.loads(
        fn(
            "fee",
            json.dumps(
                {"price": 0.5, "size": 100, "category": "finance", "is_maker": True}
            ),
        )
    )
    assert out["error"] in ("not_served", ENGINE_REQUIRED_ERR)
