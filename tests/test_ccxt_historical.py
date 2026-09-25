"""CCXTBackend.get_historical: fail-loud interval validation + real pagination.

Design doc: `plans/refactor/proposals/FINANCE-INTEGRATION-20260924.md` cites
this method (`backends.py:599` before the fix) for two bugs: history silently
truncated, and unsupported intervals silently remapped to daily bars. These
tests pin the fixed behaviour: no live network, a fake ccxt-shaped exchange.
"""

from __future__ import annotations

import pytest

from emerald_exchange.backends import (
    CCXTBackend,
    HistoricalDataError,
    TradingMode,
    UnsupportedIntervalError,
    _fetch_ccxt_ohlcv_pages,
)


class _FakeCcxtExchange:
    """A minimal stand-in for a ccxt exchange's ``fetch_ohlcv`` surface."""

    def __init__(self, pages: list[list[list[float]]], timeframes: dict | None = None):
        self._pages = list(pages)
        self.timeframes = timeframes or {}
        self.calls: list[tuple[str, str, int, int]] = []

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        self.calls.append((symbol, timeframe, since, limit))
        if not self._pages:
            return []
        return self._pages.pop(0)


def _connected_backend(exchange: _FakeCcxtExchange) -> CCXTBackend:
    backend = CCXTBackend(exchange_id="binance", mode=TradingMode.PAPER)
    backend._exchange = exchange  # simulate a completed connect()
    return backend


def _candle(ts_ms: int, price: float = 100.0) -> list[float]:
    return [ts_ms, price, price + 1, price - 1, price, 10.0]


def test_unsupported_interval_raises_instead_of_falling_back_to_daily():
    backend = _connected_backend(_FakeCcxtExchange(pages=[]))

    with pytest.raises(UnsupportedIntervalError):
        backend.get_historical("BTC/USDT", period="30d", interval="4h-typo")


def test_exchange_declared_timeframes_are_respected():
    exchange = _FakeCcxtExchange(pages=[], timeframes={"1d": "1d", "1h": "1h"})
    backend = _connected_backend(exchange)

    with pytest.raises(UnsupportedIntervalError):
        backend.get_historical("BTC/USDT", period="30d", interval="15m")


def test_disconnected_backend_fails_loud_not_empty_list():
    backend = CCXTBackend(exchange_id="binance", mode=TradingMode.PAPER)
    assert backend._exchange is None

    with pytest.raises(HistoricalDataError):
        backend.get_historical("BTC/USDT", period="30d", interval="1d")


def test_underlying_exchange_error_fails_loud():
    class _Boom(_FakeCcxtExchange):
        def fetch_ohlcv(self, *a, **kw):
            raise RuntimeError("rate limited")

    backend = _connected_backend(_Boom(pages=[]))
    with pytest.raises(HistoricalDataError):
        backend.get_historical("BTC/USDT", period="30d", interval="1d")


def test_get_historical_requests_a_1000_bar_page_size():
    """The public method's page size, visible on the fake's recorded calls."""
    exchange = _FakeCcxtExchange(pages=[[_candle(1_699_000_000_000)]])
    backend = _connected_backend(exchange)

    backend.get_historical("BTC/USDT", period="30d", interval="1d")

    assert exchange.calls[0][3] == 1000  # the `limit` argument passed through


def test_fetch_ccxt_ohlcv_pages_walks_forward_across_multiple_pages():
    """The extracted pagination helper covers more history than one page holds.

    Regression for the design-doc-cited bug: history silently truncated to a
    handful of bars. Here a 500-bar window is served in three pages of <=200,
    and every bar must be reachable — none silently dropped.
    """
    day_ms = 86_400_000
    now_ms = 1_700_000_000_000
    floor_ms = now_ms - 500 * day_ms

    page1 = [_candle(floor_ms + i * day_ms) for i in range(200)]
    page2 = [_candle(floor_ms + (200 + i) * day_ms) for i in range(200)]
    page3 = [_candle(floor_ms + (400 + i) * day_ms) for i in range(100)]
    exchange = _FakeCcxtExchange(pages=[page1, page2, page3])

    candles = _fetch_ccxt_ohlcv_pages(
        exchange, "BTC/USDT", "1d", "binance", floor_ms, now_ms, page_limit=200
    )

    assert len(exchange.calls) == 3, "must have paged across all three pages"
    assert len(candles) == 500, f"expected all 500 bars reachable, got {len(candles)}"
    timestamps = [c[0] for c in candles]
    assert timestamps == sorted(timestamps)
    assert len(timestamps) == len(set(timestamps))


def test_fetch_ccxt_ohlcv_pages_raises_when_page_budget_is_exhausted():
    """An exchange that never returns a short page cannot loop forever."""
    day_ms = 86_400_000
    now_ms = 1_700_000_000_000
    floor_ms = now_ms - 100_000 * day_ms  # an absurdly long lookback

    def _endless_full_pages():
        ts = floor_ms
        while True:
            yield [_candle(ts + i * day_ms) for i in range(200)]
            ts += 200 * day_ms

    gen = _endless_full_pages()

    class _EndlessExchange(_FakeCcxtExchange):
        def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
            self.calls.append((symbol, timeframe, since, limit))
            return next(gen)

    with pytest.raises(HistoricalDataError):
        _fetch_ccxt_ohlcv_pages(
            _EndlessExchange(pages=[]),
            "BTC/USDT",
            "1d",
            "binance",
            floor_ms,
            now_ms,
            page_limit=200,
        )


def test_short_page_stops_pagination_at_end_of_available_history():
    """A page shorter than the requested limit signals 'no more data'."""
    import time

    recent_ms = int(time.time() * 1000) - 3_600_000  # one hour ago
    exchange = _FakeCcxtExchange(pages=[[_candle(recent_ms)]])
    backend = _connected_backend(exchange)

    bars = backend.get_historical("NEWCOIN/USDT", period="365d", interval="1d")

    assert len(exchange.calls) == 1
    assert len(bars) == 1


def test_no_data_returns_empty_list_without_error():
    """A real fetch that legitimately returns nothing is not an error."""
    exchange = _FakeCcxtExchange(pages=[[]])
    backend = _connected_backend(exchange)

    bars = backend.get_historical("DELISTED/USDT", period="30d", interval="1d")

    assert bars == []


def test_invalid_period_string_fails_loud():
    exchange = _FakeCcxtExchange(pages=[])
    backend = _connected_backend(exchange)

    with pytest.raises(ValueError):
        backend.get_historical("BTC/USDT", period="not-a-period", interval="1d")
