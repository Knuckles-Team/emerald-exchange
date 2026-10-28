"""Bounded CCXT history preserves period, prices and pagination."""

import pytest

from emerald_exchange.backends import CCXTBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations

START = "2026-01-02T14:30:00Z"
END = "2026-01-02T14:35:00Z"
BASE = 1767364200000
CANDLE = [BASE, 100, 103, 99, 102, 25]


class Exchange:
    def __init__(self):
        self.calls = []

    def fetch_ohlcv(self, symbol, interval, *, since, limit):
        self.calls.append((symbol, interval, since, limit))
        if since == BASE:
            return [CANDLE]
        if since == BASE + 1:
            return [[BASE + 60000, 101, 103, 99, 102, 10]]
        return []


def test_source_pages_propagate_since_and_stable_identity():
    backend = CCXTBackend(exchange_id="binance")
    backend._exchange = exchange = Exchange()
    ops = ExchangeReadOperations(backend)
    args = {
        "symbol": "BTC/USDT",
        "start": START,
        "end": END,
        "interval": "1m",
        "license_tag": "licensed",
        "mode": "delta",
    }
    first = ops.get_exchange_history(**args)
    second = ops.get_exchange_history(**args, page_token=first["next_page_token"])
    terminal = ops.get_exchange_history(**args, page_token=second["next_page_token"])
    assert first["candles"][0]["timestamp"] == "2026-01-02T14:30:00.000Z"
    assert first["candles"][0]["exchange"] == "binance"
    assert first["candles"][0]["candle_id"] != second["candles"][0]["candle_id"]
    assert not terminal["candles"] and terminal["next_page_token"] is None
    assert [call[2] for call in exchange.calls] == [BASE, BASE + 1, BASE + 60001]
    assert (
        ops.get_exchange_history(**args)["candles"][0]["candle_id"]
        == first["candles"][0]["candle_id"]
    )


def test_legacy_history_honors_period_and_never_silently_truncates():
    from datetime import UTC, datetime

    backend = CCXTBackend()

    class Empty:
        def fetch_ohlcv(self, symbol, interval, *, since, limit):
            self.since = since
            self.interval = interval
            return []

    backend._exchange = exchange = Empty()
    assert backend.get_historical("BTC/USDT", "1d", "5m") == []
    assert exchange.interval == "5m"
    assert (
        abs(int(datetime.now(UTC).timestamp() * 1000) - exchange.since - 86_400_000)
        < 5000
    )
    with pytest.raises(ValueError):
        backend.get_historical("BTC/USDT", "unknown", "5m")

    class Long:
        def fetch_ohlcv(self, symbol, interval, *, since, limit):
            return [[since, 1, 2, 1, 2, 1]]

    backend._exchange = Long()
    with pytest.raises(RuntimeError, match="page limit"):
        backend.get_historical("BTC/USDT", "1d", "5m")


@pytest.mark.parametrize(
    "page",
    [
        [[BASE, 1, 0, 0, 1, 1]],
        [[BASE, 1, 2, 1, float("nan"), 1]],
        [CANDLE, CANDLE],
        [[BASE - 1, 1, 2, 1, 2, 1]],
    ],
)
def test_bad_exchange_pages_are_redacted(page):
    backend = CCXTBackend()

    class Bad:
        def fetch_ohlcv(self, *args, **kwargs):
            return page

    backend._exchange = Bad()
    with pytest.raises(RuntimeError, match="exchange history read failed"):
        ExchangeReadOperations(backend).get_exchange_history(
            "BTC/USDT", START, END, "1m", "licensed", "delta"
        )
