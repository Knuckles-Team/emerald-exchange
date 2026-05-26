"""Smoke tests for emerald-exchange startup. CONCEPT:EE-001"""

from emerald_exchange.backends import PaperBackend, OrderSide, TradingMode, create_backend
from emerald_exchange.risk_guards import RiskGuard, RiskLimits


def test_paper_backend_lifecycle():
    """Paper backend: connect → quote → order → positions → account."""
    backend = PaperBackend(initial_cash=50_000.0)
    backend.connect()

    assert backend.name == "paper"
    assert backend.mode == TradingMode.PAPER

    # Quote
    quote = backend.get_quote("TEST")
    assert quote.symbol == "TEST"
    assert quote.last > 0

    # Order
    result = backend.submit_order("TEST", OrderSide.BUY, 5)
    assert result.status == "filled"
    assert result.filled_qty == 5

    # Positions
    positions = backend.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "TEST"

    # Account
    acct = backend.get_account()
    assert acct.equity > 0
    assert acct.cash < 50_000.0  # Used some cash


def test_risk_guard_pre_trade():
    """Risk guard approves safe trade, rejects oversized trade."""
    guard = RiskGuard(RiskLimits(max_position_pct=0.02))

    # Safe trade: 1% of portfolio
    check = guard.pre_trade_check("TEST", 10, 100, 100_000, 100_000)
    assert check.approved
    assert check.adjusted_qty == 10

    # Oversized trade: 50% of portfolio → sized down
    check = guard.pre_trade_check("TEST", 500, 100, 100_000, 100_000)
    assert check.approved
    assert check.adjusted_qty < 500  # Risk guard sized it down


def test_risk_guard_circuit_breaker():
    """Circuit breaker triggers on excessive drawdown."""
    guard = RiskGuard(RiskLimits(max_portfolio_drawdown_pct=0.10))
    guard._peak_equity = 100_000.0

    # Safe drawdown
    check = guard.check_drawdown(95_000)
    assert check.approved

    # Breach drawdown
    check = guard.check_drawdown(85_000)
    assert not check.approved
    assert guard.is_halted


def test_risk_guard_kill_switch():
    """Kill switch halts and resumes trading."""
    guard = RiskGuard()
    assert not guard.is_halted

    guard.halt("test halt")
    assert guard.is_halted

    check = guard.pre_trade_check("TEST", 1, 100, 100_000, 100_000)
    assert not check.approved

    guard.resume()
    assert not guard.is_halted


def test_kelly_criterion():
    """Kelly criterion produces valid position sizes."""
    size = RiskGuard.kelly_criterion(0.6, 2.0, half_kelly=True, max_risk=0.02)
    assert 0 < size <= 0.02


def test_create_backend_factory():
    """Factory creates backend by name."""
    backend = create_backend("paper", {}, TradingMode.PAPER)
    assert backend.name == "paper"
    backend.connect()
    assert backend.get_account().equity > 0
