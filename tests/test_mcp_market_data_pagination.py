"""``emerald_market_data`` 'historical' action: real pagination, loud errors.

Regression for the design-doc-cited bug: `data[:50]` silently discarded every
bar past the 50th with no indication to the caller. These tests exercise the
registered tool function directly against a fake FastMCP-shaped server and a
fake backend — no live network, no real exchange.
"""

from __future__ import annotations

import json

from emerald_exchange.backends import (
    OHLCV,
    HistoricalDataError,
    UnsupportedIntervalError,
)
from emerald_exchange.mcp.mcp_market_data import (
    MAX_HISTORICAL_LIMIT,
    register_market_data_tools,
)


class _FakeMcp:
    """Enough of FastMCP's surface for `@mcp.tool(...)` registration."""

    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, **_kwargs):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class _FakeBackend:
    name = "fake"
    mode = "paper"

    def __init__(self, bars: list[OHLCV] | None = None, error: Exception | None = None):
        self._bars = bars or []
        self._error = error

    def get_quote(self, symbol):  # pragma: no cover - not exercised here
        raise NotImplementedError

    def get_historical(self, symbol, period, interval):
        if self._error is not None:
            raise self._error
        return self._bars


def _bars(n: int) -> list[OHLCV]:
    return [
        OHLCV(
            timestamp=f"2026-01-{i + 1:02d}T00:00:00Z",
            open=i,
            high=i,
            low=i,
            close=i,
            volume=i,
        )
        for i in range(n)
    ]


def _tool(backend):
    mcp = _FakeMcp()
    register_market_data_tools(mcp, backend)
    return mcp.tools["emerald_market_data"]


def test_historical_returns_every_bar_across_pages_not_just_the_first_50():
    tool = _tool(_FakeBackend(bars=_bars(120)))

    first = json.loads(tool(action="historical", symbol="BTC/USDT", limit=50, offset=0))
    assert len(first["bars"]) == 50
    assert first["total"] == 120
    assert first["has_more"] is True

    second = json.loads(
        tool(action="historical", symbol="BTC/USDT", limit=50, offset=50)
    )
    assert len(second["bars"]) == 50
    assert second["has_more"] is True

    third = json.loads(
        tool(action="historical", symbol="BTC/USDT", limit=50, offset=100)
    )
    assert len(third["bars"]) == 20
    assert third["has_more"] is False

    # No bar is ever dropped across the full page walk.
    seen = {b["t"] for b in first["bars"] + second["bars"] + third["bars"]}
    assert len(seen) == 120


def test_historical_default_limit_covers_more_than_the_old_hardcoded_50():
    tool = _tool(_FakeBackend(bars=_bars(120)))

    result = json.loads(tool(action="historical", symbol="BTC/USDT"))

    assert result["total"] == 120
    assert len(result["bars"]) == 120  # default page (500) covers all 120
    assert result["has_more"] is False


def test_historical_limit_is_capped_not_unbounded():
    tool = _tool(_FakeBackend(bars=_bars(MAX_HISTORICAL_LIMIT + 500)))

    result = json.loads(tool(action="historical", symbol="BTC/USDT", limit=999_999))

    assert result["limit"] == MAX_HISTORICAL_LIMIT
    assert len(result["bars"]) == MAX_HISTORICAL_LIMIT


def test_unsupported_interval_surfaces_as_explicit_error_not_silent_fallback():
    tool = _tool(
        _FakeBackend(error=UnsupportedIntervalError("interval '4h-typo' unsupported"))
    )

    result = json.loads(
        tool(action="historical", symbol="BTC/USDT", interval="4h-typo")
    )

    assert result["error_type"] == "unsupported_interval"
    assert "error" in result
    assert "bars" not in result


def test_historical_data_error_surfaces_as_explicit_error_not_empty_bars():
    tool = _tool(_FakeBackend(error=HistoricalDataError("fetch_ohlcv failed")))

    result = json.loads(tool(action="historical", symbol="BTC/USDT"))

    assert result["error_type"] == "historical_data_error"
    assert "bars" not in result


def test_historical_requires_symbol():
    tool = _tool(_FakeBackend(bars=_bars(5)))

    result = json.loads(tool(action="historical"))

    assert "error" in result
