"""Provider calendar classification across DST, holidays and early closes."""

from datetime import date
from types import SimpleNamespace

import pytest
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Calendar

from emerald_exchange.alpaca_sessions import classify_stock_bar_sessions
from emerald_exchange.backends import AlpacaBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations
from tests.test_alpaca_stock_bars import ARGS, BAR, Market


class CalendarClient:
    def __init__(self, days):
        self.days = days
        self.requests = []

    def get_calendar(self, request):
        self.requests.append(request)
        return self.days


def test_calendar_labels_normal_and_short_day_without_guessing_holidays():
    calendar = CalendarClient(
        [
            Calendar(date="2026-11-25", open="09:30", close="16:00"),
            Calendar(date="2026-11-27", open="09:30", close="13:00"),
        ]
    )
    bars = [
        {"timestamp": value}
        for value in (
            "2026-11-25T13:30:00Z",  # 08:30 ET, pre
            "2026-11-25T15:00:00Z",  # 10:00 ET, regular
            "2026-11-25T22:00:00Z",  # 17:00 ET, post
            "2026-11-26T15:00:00Z",  # Thanksgiving, closed
            "2026-11-27T19:00:00Z",  # 14:00 ET, no post on half-day
        )
    ]
    classify_stock_bar_sessions(calendar, bars, feed="iex", timeframe="1Min")
    assert [bar["session"] for bar in bars] == [
        "pre_market",
        "regular",
        "post_market",
        "outside_session",
        "outside_session",
    ]
    assert all(bar["session_scope"] == "alpaca_calendar" for bar in bars)
    assert calendar.requests[0].start == date(2026, 11, 25)
    assert calendar.requests[0].end == date(2026, 11, 27)


def test_backend_calendar_scopes_real_page():
    backend = AlpacaBackend()
    backend._stock_data_client = Market(
        {"bars": {"AAPL": [BAR]}, "next_page_token": None}
    )
    backend._client = CalendarClient(
        [Calendar(date="2026-01-02", open="09:30", close="16:00")]
    )
    result = ExchangeReadOperations(backend).get_stock_bars(
        **ARGS, session_scope="alpaca_calendar"
    )
    assert result["bars"][0]["session"] == "regular"


def test_official_calendar_client_parses_provider_response(monkeypatch):
    client = TradingClient("key", "secret", paper=True)
    calls = []

    def get(path, data):
        calls.append((path, data))
        return [{"date": "2026-01-02", "open": "09:30", "close": "16:00"}]

    monkeypatch.setattr(client, "get", get)
    bars = [{"timestamp": "2026-01-02T14:30:00Z"}]
    classify_stock_bar_sessions(client, bars, feed="iex", timeframe="1Min")
    assert bars[0]["session"] == "regular"
    assert calls[0][0] == "/calendar"
    assert calls[0][1] == {"start": "2026-01-02", "end": "2026-01-02"}


@pytest.mark.parametrize(
    "feed,timeframe,stamp",
    [
        ("boats", "1Min", "2026-01-02T14:30:00Z"),
        ("iex", "1Day", "2026-01-02T14:30:00Z"),
        ("iex", "1Min", "2026-01-02T14:30:00.1Z"),
    ],
)
def test_ambiguous_interval_or_feed_refuses(feed, timeframe, stamp):
    with pytest.raises(ValueError):
        classify_stock_bar_sessions(
            CalendarClient([]), [{"timestamp": stamp}], feed=feed, timeframe=timeframe
        )


def test_invalid_or_duplicate_calendar_refuses_without_partial_labels():
    bad = SimpleNamespace(date=date(2026, 1, 2), open="bad", close="bad")
    bars = [{"timestamp": "2026-01-02T14:30:00Z"}]
    with pytest.raises(TypeError):
        classify_stock_bar_sessions(
            CalendarClient([bad]), bars, feed="iex", timeframe="1Min"
        )
    assert "session" not in bars[0]
