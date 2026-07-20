"""Shared test fixtures for emerald-exchange."""

import csv

import pytest

from emerald_exchange.backends import PaperBackend, OrderSide, TradingMode
from emerald_exchange.risk_guards import RiskGuard, RiskLimits


# Synthetic Polymarket trade dataset: two wallets with resolved positions so
# win_rate / pnl / exit metrics are testable end-to-end with the stdlib CSV
# reader (no polars required).
_TRADE_ROWS = [
    # winner: buys YES low, holds to a winning resolution
    {"wallet": "0xWINNER", "market_id": "m1", "token": "tYES", "side": "BUY",
     "price": "0.40", "usd_amount": "40", "shares": "100", "timestamp": "100",
     "resolved": "true", "won": "true", "payout": "100"},
    # winner: a second winning market
    {"wallet": "0xWINNER", "market_id": "m2", "token": "tA", "side": "BUY",
     "price": "0.50", "usd_amount": "50", "shares": "100", "timestamp": "200",
     "resolved": "true", "won": "true", "payout": "100"},
    # winner: a losing market (so win_rate < 1.0)
    {"wallet": "0xWINNER", "market_id": "m3", "token": "tB", "side": "BUY",
     "price": "0.60", "usd_amount": "60", "shares": "100", "timestamp": "300",
     "resolved": "true", "won": "false", "payout": "0"},
    # loser: buys high, loses
    {"wallet": "0xLOSER", "market_id": "m1", "token": "tNO", "side": "BUY",
     "price": "0.60", "usd_amount": "60", "shares": "100", "timestamp": "110",
     "resolved": "true", "won": "false", "payout": "0"},
    # loser: exits early (sells before resolution)
    {"wallet": "0xLOSER", "market_id": "m4", "token": "tC", "side": "BUY",
     "price": "0.50", "usd_amount": "50", "shares": "100", "timestamp": "120",
     "resolved": "false", "won": "", "payout": ""},
    {"wallet": "0xLOSER", "market_id": "m4", "token": "tC", "side": "SELL",
     "price": "0.55", "usd_amount": "55", "shares": "100", "timestamp": "130",
     "resolved": "false", "won": "", "payout": ""},
]

_TRADE_FIELDS = [
    "wallet", "market_id", "token", "side", "price", "usd_amount",
    "shares", "timestamp", "resolved", "won", "payout",
]


@pytest.fixture
def trades_csv(tmp_path):
    """Write the synthetic trade dataset to a tmp CSV and return its path."""
    path = tmp_path / "trades.csv"
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TRADE_FIELDS)
        writer.writeheader()
        writer.writerows(_TRADE_ROWS)
    return str(path)


@pytest.fixture
def engine_client():
    """Return a live epistemic-graph client, or skip if none is reachable.

    Engine-backed assertions (market-making quotes, Bayesian Kelly, backtest
    validation, forensic screen) gate on this so the suite passes cleanly in
    offline / no-socket environments.
    """
    from emerald_exchange._engine import finance_engine

    client = finance_engine()
    if client is None:
        pytest.skip("epistemic-graph engine not reachable (set EPISTEMIC_GRAPH_SOCKET)")
    return client


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
