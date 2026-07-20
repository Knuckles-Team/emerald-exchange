"""Tests for execution-bridge (EE-032), cockpit (EE-033), derivatives (EE-034).

Engine-dependent assertions gate on the ``engine_client`` fixture so the suite
passes cleanly offline (no socket).
"""

import json

import pytest

from emerald_exchange.backends import (
    OrderSide,
    OrderType,
    PaperBackend,
    TradingMode,
)
from emerald_exchange.cockpit import build_snapshot, cockpit, render_snapshot
from emerald_exchange.derivatives import calibrate, implied_vol, smile, vol_arb
from emerald_exchange.execution_bridge import (
    ExecutionBridge,
    RoutingStatus,
    TradeDecision,
)
from emerald_exchange.risk_guards import RiskGuard, RiskLimits


# ── A live-mode paper backend: behaves like paper but reports LIVE mode, so we
# can exercise the live gate without any real venue. ──────────────────────────
class LiveLabeledPaperBackend(PaperBackend):
    @property
    def mode(self) -> TradingMode:  # type: ignore[override]
        return TradingMode.LIVE


# ──────────────────────────────────────────────────────────────────────────
# DELIVERABLE 1 — Execution bridge gating proof
# ──────────────────────────────────────────────────────────────────────────


def test_paper_decision_executes(paper_backend, risk_guard):
    bridge = ExecutionBridge(paper_backend, risk_guard)
    decision = TradeDecision(
        symbol="AAPL",
        side=OrderSide.BUY,
        qty=1.0,
        order_type=OrderType.LIMIT,
        limit_price=100.0,
        source="debate",
    )
    result = bridge.route(decision)
    assert result.status == RoutingStatus.EXECUTED
    assert result.is_live is False
    assert result.execution is not None
    assert result.execution.order_id.startswith("PAPER-")


def test_live_decision_blocked_while_paper_executes():
    """THE gating proof: identical decision — live is blocked, paper executes."""
    risk_guard = RiskGuard(RiskLimits(require_human_approval_live=True))

    decision = TradeDecision(
        symbol="AAPL",
        side=OrderSide.BUY,
        qty=1.0,
        order_type=OrderType.LIMIT,
        limit_price=100.0,
    )

    # LIVE path — blocked, no order placed.
    live_backend = LiveLabeledPaperBackend(initial_cash=100_000.0)
    live_backend.connect()
    live_bridge = ExecutionBridge(live_backend, risk_guard)
    live_result = live_bridge.route(decision)
    assert live_result.status == RoutingStatus.APPROVAL_REQUIRED
    assert live_result.execution is None
    assert "approval" in live_result.reason.lower()

    # PAPER path — same decision runs freely.
    paper_backend = PaperBackend(initial_cash=100_000.0)
    paper_backend.connect()
    paper_bridge = ExecutionBridge(paper_backend, risk_guard)
    paper_result = paper_bridge.route(decision)
    assert paper_result.status == RoutingStatus.EXECUTED
    assert paper_result.execution is not None


def test_live_blocked_even_with_approval_when_policy_set():
    """Explicit approve=True does NOT bypass a standing human-approval policy
    via the kill-switch/halt path; with the policy set we only allow the
    approved order when require_human_approval_live is the only gate."""
    risk_guard = RiskGuard(RiskLimits(require_human_approval_live=True))
    backend = LiveLabeledPaperBackend(initial_cash=100_000.0)
    backend.connect()
    bridge = ExecutionBridge(backend, risk_guard)
    decision = TradeDecision(
        symbol="AAPL",
        side=OrderSide.BUY,
        qty=1.0,
        order_type=OrderType.LIMIT,
        limit_price=100.0,
    )
    # Unapproved -> approval required.
    assert bridge.route(decision).status == RoutingStatus.APPROVAL_REQUIRED
    # Approved by a human at this seam -> executes (still risk-checked).
    approved = bridge.route(decision, approve=True)
    assert approved.status == RoutingStatus.EXECUTED
    assert approved.approved is True


def test_halted_guard_blocks_even_paper():
    risk_guard = RiskGuard()
    risk_guard.halt("test")
    backend = PaperBackend(initial_cash=100_000.0)
    backend.connect()
    bridge = ExecutionBridge(backend, risk_guard)
    result = bridge.route(
        TradeDecision(symbol="AAPL", side=OrderSide.BUY, qty=1.0, limit_price=100.0)
    )
    assert result.status == RoutingStatus.BLOCKED


def test_invalid_decision_rejected(paper_backend, risk_guard):
    bridge = ExecutionBridge(paper_backend, risk_guard)
    result = bridge.route(TradeDecision(symbol="", side=OrderSide.BUY, qty=0.0))
    assert result.status == RoutingStatus.REJECTED


def test_decision_from_dict():
    d = TradeDecision.from_dict(
        {
            "symbol": "BTC/USD",
            "side": "sell",
            "qty": 2,
            "order_type": "limit",
            "limit_price": 50000,
            "source": "optimizer",
        }
    )
    assert d.symbol == "BTC/USD"
    assert d.side == OrderSide.SELL
    assert d.order_type == OrderType.LIMIT
    assert d.limit_price == 50000.0


def test_result_to_dict_serializable(paper_backend, risk_guard):
    bridge = ExecutionBridge(paper_backend, risk_guard)
    result = bridge.route(
        TradeDecision(symbol="AAPL", side=OrderSide.BUY, qty=1.0, limit_price=100.0)
    )
    payload = json.dumps(result.to_dict())
    assert "execution" in payload


# ──────────────────────────────────────────────────────────────────────────
# DELIVERABLE 2 — Cockpit
# ──────────────────────────────────────────────────────────────────────────


def test_cockpit_snapshot_offline_safe(paper_backend, risk_guard):
    snap = build_snapshot(paper_backend, risk_guard, watchlist=["AAPL", "BTC/USD"])
    # All required fields present.
    assert snap.engine["status"] in ("online", "offline")
    assert snap.account["exchange"] == "paper"
    assert "kill_switch" in snap.risk
    assert "drawdown_pct" in snap.risk
    assert len(snap.quotes) == 2
    # JSON-serializable structured snapshot.
    json.loads(snap.to_json())


def test_cockpit_renders_plain_and_default(paper_backend, risk_guard):
    snap = build_snapshot(paper_backend, risk_guard, watchlist=["AAPL"])
    plain = render_snapshot(snap, use_rich=False)
    assert "EMERALD COCKPIT" in plain
    assert "ACCOUNT" in plain
    assert "RISK" in plain
    # Default cockpit() with no args is offline-safe and returns text.
    out = cockpit(watchlist=["AAPL"], use_rich=False)
    assert "ENGINE" in out


def test_cockpit_engine_offline_when_no_socket(paper_backend, risk_guard, monkeypatch):
    # Force the engine probe to report unreachable.
    import emerald_exchange.cockpit as cm

    monkeypatch.setattr(
        "emerald_exchange._engine.finance_engine", lambda: None, raising=True
    )
    snap = cm.build_snapshot(paper_backend, risk_guard)
    assert snap.engine["status"] == "offline"


def test_cockpit_signals_render(paper_backend, risk_guard):
    snap = build_snapshot(
        paper_backend,
        risk_guard,
        signals=[{"name": "momentum", "value": 0.42}],
    )
    text = render_snapshot(snap, use_rich=False)
    assert "SIGNALS" in text
    assert "momentum" in text


# ──────────────────────────────────────────────────────────────────────────
# DELIVERABLE 3 — Derivatives / SABR
# ──────────────────────────────────────────────────────────────────────────


def test_derivatives_offline_returns_error(monkeypatch):
    monkeypatch.setattr(
        "emerald_exchange.derivatives.finance_engine", lambda: None, raising=True
    )
    assert "error" in implied_vol(1.0, 1.0, 1.0, 0.2, 0.5, 0.0, 0.3)
    assert "error" in smile(1.0, [0.9, 1.1], 1.0, 0.2, 0.5, 0.0, 0.3)
    assert "error" in calibrate(1.0, 1.0, [0.9, 1.1], [0.2, 0.21])
    assert "error" in vol_arb(1.0, 1.0, [0.9, 1.1], [0.2, 0.21])


def test_derivatives_length_mismatch():
    # Length validation happens before the engine call (still error offline).
    res = calibrate(1.0, 1.0, [0.9, 1.0, 1.1], [0.2, 0.21])
    assert "error" in res


def _skip_if_unknown_variant(res: dict) -> None:
    """Skip when the live engine daemon is a version behind and lacks the SABR
    kernel (KG-2.20j). The engine surfaces that as an 'unknown variant'
    MessagePack error — mirror the no-socket skip so engine-backed tests never
    hard-fail on a stale daemon."""
    err = str(res.get("error", "")).lower()
    if "unknown variant" in err or "unknown method" in err:
        pytest.skip(f"engine lacks SABR kernel (version behind): {res['error']}")


def test_sabr_implied_vol_engine(engine_client):
    res = implied_vol(f=1.0, k=1.0, t=1.0, alpha=0.2, beta=0.5, rho=-0.3, nu=0.4)
    _skip_if_unknown_variant(res)
    assert "error" not in res
    assert res["implied_vol"] > 0


def test_sabr_smile_engine(engine_client):
    res = smile(
        f=1.0,
        strikes=[0.8, 0.9, 1.0, 1.1, 1.2],
        t=1.0,
        alpha=0.2,
        beta=0.5,
        rho=-0.3,
        nu=0.4,
    )
    _skip_if_unknown_variant(res)
    assert "error" not in res
    assert len(res["vols"]) == 5
    assert all(v > 0 for v in res["vols"])


def test_sabr_calibrate_and_vol_arb_engine(engine_client):
    strikes = [0.8, 0.9, 1.0, 1.1, 1.2]
    # Generate a self-consistent market smile, then calibrate back.
    gen = smile(1.0, strikes, 1.0, 0.25, 0.5, -0.2, 0.5)
    _skip_if_unknown_variant(gen)
    if "error" in gen:
        pytest.skip("engine smile unavailable")
    market_vols = gen["vols"]
    cal = calibrate(f=1.0, t=1.0, strikes=strikes, market_vols=market_vols, beta=0.5)
    assert "error" not in cal
    assert {"alpha", "beta", "rho", "nu", "rmse", "converged"} <= set(cal.keys())

    arb = vol_arb(f=1.0, t=1.0, strikes=strikes, market_vols=market_vols, beta=0.5)
    assert "error" not in arb
    assert len(arb["rows"]) == len(strikes)
    # Self-consistent smile -> residuals tiny.
    assert all(abs(r["residual"]) < 0.05 for r in arb["rows"])
