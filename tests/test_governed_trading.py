"""The governed backend: paper by default, no live effect outside D18 (EH-423)."""

from __future__ import annotations

import json

import pytest

from emerald_exchange.backends import (
    AccountInfo,
    ExecutionResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    TradingMode,
)
from emerald_exchange.execution_bridge import (
    ExecutionBridge,
    RoutingStatus,
    TradeDecision,
)
from emerald_exchange.mcp.mcp_orders import register_order_tools
from emerald_exchange.mcp_server import build_trading_backends
from emerald_exchange.risk_guards import RiskGuard, RiskLimits
from emerald_exchange.trading import GovernedBackend, LiveOrderRefused


class LiveVenue:
    """A venue in live mode that records every effect it is asked for."""

    name = "live-venue"
    mode = TradingMode.LIVE
    supported_assets = ("equity",)

    def __init__(self, quote: Quote | None = None) -> None:
        self.effects: list[tuple[str, tuple]] = []
        self._quote = quote or Quote("AAPL", bid=99.0, ask=101.0, last=100.0, volume=1)

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        return None

    def submit_order(self, *args: object) -> ExecutionResult:
        self.effects.append(("submit", args))
        return ExecutionResult("V-1", OrderStatus.FILLED, 1, 100.0, 0.0, self.name)

    def cancel_order(self, order_id: str) -> bool:
        self.effects.append(("cancel", (order_id,)))
        return True

    def get_order_status(self, order_id: str) -> ExecutionResult:
        return ExecutionResult(order_id, OrderStatus.FILLED, 1, 100.0, 0.0, self.name)

    def get_positions(self) -> list[Position]:
        return [Position("AAPL", 3, 90.0, 100.0, 30.0, "long", self.name)]

    def get_account(self) -> AccountInfo:
        return AccountInfo(equity=1_000.0, cash=700.0, buying_power=700.0)

    def get_quote(self, symbol: str) -> Quote:
        return self._quote

    def get_historical(self, symbol: str, period: str = "1y", interval: str = "1d"):
        return []


class _CaptureMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):
        def _wrap(fn):
            self.tools[fn.__name__] = fn
            return fn

        return _wrap


def test_paper_is_the_default_and_fills_at_the_venue_quote() -> None:
    venue = LiveVenue()
    governed = GovernedBackend(venue)
    assert governed.mode == TradingMode.PAPER
    buy = governed.submit_order("AAPL", OrderSide.BUY, 2)
    sell = governed.submit_order("AAPL", OrderSide.SELL, 1)
    assert buy.order_id.startswith("PAPER-") and buy.average_price == 101.0
    assert sell.average_price == 99.0
    assert venue.effects == []
    [position] = governed.get_positions()
    assert position.qty == 1 and position.current_price == 100.0


def test_a_paper_order_without_a_quote_is_rejected_not_invented() -> None:
    venue = LiveVenue(Quote("X", bid=0.0, ask=0.0, last=0.0, volume=0))
    result = GovernedBackend(venue).submit_order("X", OrderSide.BUY, 1)
    assert result.status == OrderStatus.REJECTED
    assert venue.effects == []


def test_live_mode_refuses_every_effect_and_reads_the_real_account() -> None:
    venue = LiveVenue()
    governed = GovernedBackend(venue, TradingMode.LIVE)
    with pytest.raises(LiveOrderRefused):
        governed.submit_order("AAPL", OrderSide.BUY, 1, OrderType.LIMIT, 100.0)
    with pytest.raises(LiveOrderRefused):
        governed.cancel_order("V-1")
    assert venue.effects == []
    assert governed.get_positions()[0].qty == 3
    assert governed.venue_account().equity == 1_000.0


def test_the_order_tool_answers_approval_required_in_live_mode() -> None:
    venue = LiveVenue()
    mcp = _CaptureMCP()
    register_order_tools(mcp, GovernedBackend(venue, TradingMode.LIVE), RiskGuard())
    orders = mcp.tools["emerald_orders"]
    for action in ("submit", "cancel"):
        answer = json.loads(orders(action=action, symbol="AAPL", qty=1, order_id="V-1"))
        assert answer["status"] == "approval_required"
        assert "execute_approved" in answer["how"]
    assert venue.effects == []


def test_the_bridge_has_no_approval_override_for_live() -> None:
    venue = LiveVenue()
    bridge = ExecutionBridge(
        GovernedBackend(venue, TradingMode.LIVE),
        RiskGuard(
            RiskLimits(require_human_approval_live=False, stage="bounded_autonomous")
        ),
    )
    decision = TradeDecision(
        symbol="AAPL", side=OrderSide.BUY, qty=1.0, limit_price=100.0
    )
    result = bridge.route(decision)
    assert result.status == RoutingStatus.APPROVAL_REQUIRED
    assert result.execution is None
    override: dict[str, object] = {"approve": True}
    with pytest.raises(TypeError):
        bridge.route(decision, **override)
    assert venue.effects == []


def test_the_server_builds_a_governed_paper_backend_by_default() -> None:
    venue, surface, mode = build_trading_backends({}, lambda name, default: default)
    assert mode == TradingMode.PAPER
    assert isinstance(surface, GovernedBackend)
    assert surface is not venue


def test_the_positions_snapshot_is_read_only_venue_plus_paper_pnl() -> None:
    from emerald_exchange.mcp.mcp_portfolio import register_portfolio_tools

    venue = LiveVenue()
    governed = GovernedBackend(venue)
    governed.submit_order("AAPL", OrderSide.BUY, 2)
    mcp = _CaptureMCP()
    register_portfolio_tools(mcp, governed)
    snapshot = json.loads(mcp.tools["emerald_positions_snapshot"]())
    assert snapshot["mode"] == "paper" and snapshot["informational_only"] is True
    assert snapshot["venue"]["positions"][0]["qty"] == 3
    assert snapshot["venue"]["account"]["equity"] == 1_000.0
    [paper] = snapshot["paper"]["positions"]
    assert paper["qty"] == 2 and paper["current"] == 100.0
    assert snapshot["paper"]["unrealized_pnl"] == (100.0 - 101.0) * 2
    assert venue.effects == []
