"""Shared test fixtures for emerald-exchange."""

import pytest

from emerald_exchange.backends import PaperBackend, OrderSide, TradingMode
from emerald_exchange.risk_guards import RiskGuard, RiskLimits


@pytest.fixture
def paper_backend():
    """Create a paper trading backend with 100k initial cash."""
    backend = PaperBackend(initial_cash=100_000.0)
    backend.connect()
    return backend


@pytest.fixture
def risk_guard():
    """Create a risk guard with default limits."""
    return RiskGuard()


@pytest.fixture
def strict_risk_guard():
    """Create a risk guard with strict limits for testing circuit breakers."""
    return RiskGuard(
        RiskLimits(
            max_position_pct=0.01,
            max_portfolio_drawdown_pct=0.05,
            max_daily_loss_pct=0.02,
        )
    )
