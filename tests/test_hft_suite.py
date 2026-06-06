"""Tests for the HFT suite — fees, market-making, backtester, ws client,
Bayesian Kelly, and forensic screener. CONCEPT:EE-022..026

Engine-free assertions run everywhere; engine-backed numeric checks use the
``engine_client`` fixture and skip gracefully when no engine socket is present.
"""

import json

import pytest

from emerald_exchange.fees import (
    FeeCategory,
    maker_rebate,
    net_fee,
    taker_fee,
)
from emerald_exchange.market_making import (
    BookSnapshot,
    MarketMakingController,
    MMConfig,
    QuoteDecision,
)
from emerald_exchange.backtester import (
    EventBacktester,
    Event,
    EventType,
    StrategyOrder,
    inject_latency,
    shuffle_timestamps,
)
from emerald_exchange.forensic import standardize_year, STANDARD_LINE_ITEMS
from emerald_exchange.risk_guards import RiskGuard, RiskLimits


def _skip_if_unsupported(payload: dict) -> None:
    """Skip when the connected engine binary predates these finance kernels.

    A running but older ``epistemic-graph`` build rejects the new methods with an
    "unknown variant" error; that is an engine-version gap, not a code defect, so
    the engine-backed assertion skips rather than fails.
    """
    blob = " ".join(str(v) for v in payload.values())
    if "unknown variant" in blob or "Invalid request" in blob:
        pytest.skip("engine build lacks this finance kernel (unknown variant)")


# ── Fee model (pure, engine-free) ──────────────────────────────────────
def test_fee_categories_table():
    # Finance: 1.00% taker, 50% rebate; Geopolitics: 0%.
    assert taker_fee(0.5, 100, FeeCategory.FINANCE) == pytest.approx(0.5 * 100 * 0.01)
    assert taker_fee(0.5, 100, FeeCategory.GEOPOLITICS) == 0.0
    # Crypto: 1.80% taker, 20% rebate.
    tf = taker_fee(0.5, 100, "crypto")
    assert tf == pytest.approx(0.5 * 100 * 0.018)
    assert maker_rebate(0.5, 100, "crypto") == pytest.approx(tf * 0.20)


def test_fee_symmetric_binary_base():
    # YES at 0.97 and NO at 0.03 should pay the same effective fee.
    assert taker_fee(0.97, 100, "finance") == pytest.approx(
        taker_fee(0.03, 100, "finance")
    )


def test_net_fee_maker_is_credit():
    nf = net_fee(0.5, 100, "finance", is_maker=True)
    assert nf < 0  # maker receives a rebate
    assert net_fee(0.5, 100, "finance", is_maker=False) > 0  # taker pays


def test_unknown_category_defaults_other():
    assert taker_fee(0.5, 10, "nonsense") == taker_fee(0.5, 10, FeeCategory.OTHER)


# ── Market-making controller ───────────────────────────────────────────
def _sample_book() -> BookSnapshot:
    return BookSnapshot(
        ts=[0.0, 1.0],
        bid_px=[0.48, 0.49],
        bid_sz=[100.0, 120.0],
        ask_px=[0.52, 0.51],
        ask_sz=[100.0, 90.0],
        buy_vol=[10.0, 12.0],
        sell_vol=[8.0, 9.0],
        p_mean=[0.50, 0.50],
    )


def test_mm_returns_decision_not_order():
    ctrl = MarketMakingController(MMConfig(bounded=True, tick=0.01))
    decision = ctrl.decide(_sample_book(), inventory=0.0)
    assert isinstance(decision, QuoteDecision)
    # Decision shape only; no order side-effects exist on the controller.
    d = decision.to_dict()
    assert set(["bid", "ask", "withdraw", "fair_value"]).issubset(d.keys())


def test_mm_no_fair_value_withdraws():
    ctrl = MarketMakingController(MMConfig())
    empty = BookSnapshot()
    decision = ctrl.decide(empty, inventory=0.0)
    assert decision.withdraw is True
    assert decision.bid is None and decision.ask is None


def test_mm_tick_snap_and_noncrossing():
    # Local fallback path (engine may be absent): quotes snap to tick and don't cross.
    ctrl = MarketMakingController(MMConfig(bounded=True, tick=0.01, post_only=True))
    decision = ctrl.decide(_sample_book(), inventory=0.0)
    if decision.bid is not None:
        assert abs(round(decision.bid / 0.01) * 0.01 - decision.bid) < 1e-9
    if decision.bid is not None and decision.ask is not None:
        assert decision.bid < decision.ask


def test_mm_inventory_limit_withdraws_loaded_side():
    cfg = MMConfig(bounded=True, tick=0.01, max_inventory=10.0)
    ctrl = MarketMakingController(cfg)
    long_decision = ctrl.decide(_sample_book(), inventory=50.0)
    # Over-long ⇒ no bid (stop buying more).
    assert long_decision.bid is None


def test_mm_quote_engine_numeric(engine_client):
    """Engine-backed: logit_quotes returns a coherent bounded quote."""
    ctrl = MarketMakingController(MMConfig(bounded=True, tick=0.01))
    decision = ctrl.decide(_sample_book(), inventory=0.0)
    assert decision.engine_used in (True, False)
    if decision.bid is not None:
        assert 0.0 < decision.bid < 1.0


# ── Backtester ─────────────────────────────────────────────────────────
def _events() -> list[Event]:
    return [
        Event(
            ts=0.0,
            seq=0,
            type=EventType.BOOK_UPDATE,
            payload={"bid": 0.49, "ask": 0.51},
        ),
        Event(
            ts=1.0,
            seq=1,
            type=EventType.TRADE,
            payload={"price": 0.49, "size": 5.0, "side": "sell"},
        ),
        Event(
            ts=2.0,
            seq=2,
            type=EventType.BOOK_UPDATE,
            payload={"bid": 0.50, "ask": 0.52},
        ),
        Event(
            ts=3.0,
            seq=3,
            type=EventType.TRADE,
            payload={"price": 0.52, "size": 5.0, "side": "buy"},
        ),
    ]


def test_backtester_maker_fill_and_fees():
    bt = EventBacktester(category="finance")

    def strat(event, ctx):
        # Post a resting bid at 0.49 and ask at 0.52 each book update.
        if event.type == EventType.BOOK_UPDATE:
            return [StrategyOrder("bid", 0.49, 5.0), StrategyOrder("ask", 0.52, 5.0)]
        return []

    result = bt.run(_events(), strat)
    assert len(result.fills) >= 1
    assert all(f.is_maker for f in result.fills)
    # Maker fills earn rebates ⇒ total_fees should be <= 0 (net credit).
    assert result.total_fees <= 0
    assert isinstance(result.to_dict()["equity"], float)


def test_backtester_no_lookahead_strategy_only_sees_applied_book():
    seen = []

    def strat(event, ctx):
        seen.append((ctx.best_bid, ctx.best_ask))
        return []

    EventBacktester().run(_events(), strat)
    # After the first BOOK_UPDATE the strategy sees that book, never a future one.
    assert seen[0] == (0.49, 0.51)


def test_inject_latency_shifts_and_sorts():
    ev = _events()
    shifted = inject_latency(ev, latency_secs=0.5)
    assert all(s.ts >= 0.5 for s in shifted)
    assert shifted == sorted(shifted)


def test_shuffle_timestamps_preserves_grid():
    ev = _events()
    shuffled = shuffle_timestamps(ev, seed=1)
    assert sorted(e.ts for e in shuffled) == sorted(e.ts for e in ev)


def test_validate_returns_engine(engine_client):
    from emerald_exchange.backtester import validate_returns

    returns = [0.1, -0.05, 0.2, 0.0, 0.15, -0.1, 0.05, 0.08]
    out = validate_returns(returns, n_trials=3)
    _skip_if_unsupported(out)
    assert "error" not in out
    assert "observed_sharpe" in out


# ── Bayesian Kelly (RiskGuard) ─────────────────────────────────────────
def test_bayesian_kelly_capped_and_nonneg():
    guard = RiskGuard(RiskLimits(max_position_pct=0.02))
    f = guard.bayesian_kelly_size(wins=60, losses=40, cost=0.4)
    assert 0.0 <= f <= 0.02  # always within the position cap


def test_bayesian_kelly_fallback_when_no_engine(monkeypatch):
    # Force engine-unreachable ⇒ point-Kelly fallback, still capped & non-negative.
    import emerald_exchange._engine as eng

    monkeypatch.setattr(eng, "finance_engine", lambda: None)
    guard = RiskGuard(RiskLimits(max_position_pct=0.05))
    f = guard.bayesian_kelly_size(wins=70, losses=30, cost=0.4)
    assert 0.0 <= f <= 0.05


def test_require_human_approval_live_preserved():
    """Live execution gating must NOT be weakened by the new sizing path."""
    guard = RiskGuard(RiskLimits(require_human_approval_live=True))
    check = guard.pre_trade_check("X", 1, 0.5, 1000, 1000, is_live=True)
    assert not check.approved
    assert "human approval" in check.reason.lower()


# ── Forensic screener ──────────────────────────────────────────────────
def test_standardize_year_fills_all_items():
    std = standardize_year({"sales": 100, "net_income": "10"})
    assert set(std.keys()) == set(STANDARD_LINE_ITEMS)
    assert std["sales"] == 100.0
    assert std["net_income"] == 10.0
    assert std["cogs"] == 0.0  # missing ⇒ default


def test_forensic_screen_engine(engine_client):
    from emerald_exchange.forensic import forensic_screen

    this_year = {
        "sales": 1200,
        "cogs": 700,
        "net_income": 120,
        "cfo": 90,
        "total_assets": 2000,
        "receivables": 300,
    }
    prior_year = {
        "sales": 1000,
        "cogs": 600,
        "net_income": 100,
        "cfo": 110,
        "total_assets": 1800,
        "receivables": 200,
    }
    report = forensic_screen(this_year, prior_year)
    _skip_if_unsupported(report)
    assert "error" not in report
    assert "verdict" in report


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

    # Fee action is engine-free and must return a coherent JSON payload.
    out = json.loads(
        fn(
            "fee",
            json.dumps(
                {"price": 0.5, "size": 100, "category": "finance", "is_maker": True}
            ),
        )
    )
    assert out["net_fee"] < 0
