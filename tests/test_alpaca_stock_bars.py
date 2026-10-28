"""Alpaca stock pages preserve their actual provider data and labels."""

import pytest

from emerald_exchange.backends import AlpacaBackend, PaperBackend
from emerald_exchange.connector_sources import declaration
from emerald_exchange.exchange_operations import ExchangeReadOperations

BAR = {"t": "2026-01-02T14:30:00Z", "o": 100, "h": 103, "l": 99, "c": 102, "v": 25}
ARGS = {
    "symbol": "AAPL",
    "start": "2026-01-01T00:00:00Z",
    "end": "2026-01-03T00:00:00Z",
    "timeframe": "1Min",
    "adjustment": "split",
    "feed": "iex",
    "license_tag": "licensed",
    "mode": "delta",
}


class Market:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, path, data):
        self.calls.append((path, data))
        return self.response


def operations(response):
    backend = AlpacaBackend()
    backend._stock_data_client = Market(response)
    return ExchangeReadOperations(backend), backend._stock_data_client


def test_declared_stock_page_uses_provider_values_and_explicit_labels():
    source = next(
        s for s in declaration().sources if s.source_id == "alpaca-stock-bars"
    )
    assert source.tools == ("emerald_exchange_get_stock_bars",)
    ops, market = operations({"bars": {"AAPL": [BAR]}, "next_page_token": "next"})
    result = ops.get_stock_bars(**ARGS)
    assert result["next_page_token"] == "next"
    bar = result["bars"][0]
    assert (bar["symbol"], bar["open"], bar["close"], bar["volume"]) == (
        "AAPL",
        100,
        102,
        25,
    )
    assert (
        bar["adjustment"],
        bar["feed"],
        bar["session_scope"],
        bar["license_tag"],
    ) == ("split", "iex", "feed_native", "licensed")
    assert market.calls[0][0] == "/stocks/bars"
    assert market.calls[0][1]["adjustment"] == "split"
    assert market.calls[0][1]["feed"] == "iex"
    assert result["checkpoint"]["cursor"] == "next"
    assert result["checkpoint"] != ops.get_stock_bars(**ARGS)["checkpoint"]


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"bars": {"OTHER": [BAR]}, "next_page_token": None},
        {"bars": {"AAPL": []}, "next_page_token": "next"},
        {"bars": {"AAPL": [BAR, BAR]}, "next_page_token": None},
        {"bars": {"AAPL": [{**BAR, "c": float("nan")}]}, "next_page_token": None},
        {"bars": {"AAPL": [{**BAR, "h": 1}]}, "next_page_token": None},
    ],
)
def test_bad_provider_pages_refuse_without_echoing_provider_values(response):
    ops, _ = operations(response)
    with pytest.raises(RuntimeError, match="stock data read failed") as error:
        ops.get_stock_bars(**ARGS)
    assert "AAPL" not in str(error.value)


def test_repeated_page_token_and_invalid_request_refuse():
    ops, _ = operations({"bars": {"AAPL": [BAR]}, "next_page_token": "same"})
    with pytest.raises(RuntimeError, match="stock data read failed"):
        ops.get_stock_bars(**ARGS, page_token="same")
    with pytest.raises(ValueError, match="Alpaca"):
        ExchangeReadOperations(PaperBackend()).get_stock_bars(**ARGS)
    with pytest.raises(RuntimeError, match="page API"):
        ops.get_historical("AAPL")


def test_provider_error_is_redacted():
    ops, market = operations({})

    def fail(_path, data):
        raise ConnectionError("provider-private-data")

    market.get = fail
    with pytest.raises(RuntimeError) as error:
        ops.get_stock_bars(**ARGS)
    assert "provider-private-data" not in str(error.value)


QUOTE = {
    "t": "2026-01-02T14:30:00.123456789Z",
    "bp": 100,
    "ap": 101,
    "bs": 2,
    "as": 3,
    "bx": "Q",
    "ax": "N",
    "c": ["R"],
    "z": "C",
}


def test_quote_source_preserves_provider_quote_and_nanoseconds():
    source = next(
        s for s in declaration().sources if s.source_id == "alpaca-stock-quotes"
    )
    assert source.tools == ("emerald_exchange_get_stock_quote",)
    ops, market = operations({"quotes": {"AAPL": QUOTE}})
    result = ops.get_stock_quote("AAPL", "iex", "licensed", "delta")
    quote = result["quotes"][0]
    assert (quote["bid"], quote["ask"], quote["bid_size"], quote["ask_size"]) == (
        100,
        101,
        2,
        3,
    )
    assert quote["timestamp"] == "2026-01-02T14:30:00.123456789Z"
    assert (quote["feed"], quote["session_scope"], quote["conditions"]) == (
        "iex",
        "feed_native",
        ["R"],
    )
    assert market.calls[0][0] == "/stocks/quotes/latest"
    assert (
        ops.get_stock_quote("AAPL", "iex", "licensed", "delta")["quotes"][0]["quote_id"]
        == quote["quote_id"]
    )
    market.response = {
        "quotes": {"AAPL": {**QUOTE, "t": "2026-01-02T14:30:00.123456780Z"}}
    }
    assert (
        ops.get_stock_quote("AAPL", "iex", "licensed", "delta")["quotes"][0]["quote_id"]
        != quote["quote_id"]
    )
    with pytest.raises(RuntimeError, match="stock-quote API"):
        ops.get_quote("AAPL")


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"quotes": {}},
        {"quotes": {"OTHER": QUOTE}},
        {"quotes": {"AAPL": {**QUOTE, "bp": float("nan")}}},
        {"quotes": {"AAPL": {**QUOTE, "bs": -1}}},
        {"quotes": {"AAPL": {**QUOTE, "c": "private-value"}}},
    ],
)
def test_bad_quote_response_refuses_without_echoing_details(response):
    ops, _ = operations(response)
    with pytest.raises(RuntimeError, match="stock data read failed") as error:
        ops.get_stock_quote("AAPL", "iex", "licensed", "delta")
    assert "private-value" not in str(error.value)


def test_bar_identity_preserves_nanoseconds_and_equivalent_offsets():
    first = {**BAR, "t": "2026-01-02T14:30:00.123456789Z"}
    second = {**BAR, "t": "2026-01-02T09:30:00.123456789-05:00"}
    ops, market = operations({"bars": {"AAPL": [first]}, "next_page_token": None})
    record = ops.get_stock_bars(**ARGS)["bars"][0]
    market.response = {"bars": {"AAPL": [second]}, "next_page_token": None}
    assert ops.get_stock_bars(**ARGS)["bars"][0]["bar_id"] == record["bar_id"]
    market.response = {
        "bars": {"AAPL": [{**BAR, "t": "2026-01-02T14:30:00.123456780Z"}]},
        "next_page_token": None,
    }
    assert ops.get_stock_bars(**ARGS)["bars"][0]["bar_id"] != record["bar_id"]


def test_failed_stock_client_creation_does_not_leave_partial_connection(monkeypatch):
    from alpaca.data.historical import stock
    from alpaca.trading import client

    monkeypatch.setattr(client, "TradingClient", lambda *args, **kwargs: object())

    def fail(*args, **kwargs):
        raise ImportError("synthetic failure")

    monkeypatch.setattr(stock, "StockHistoricalDataClient", fail)
    backend = AlpacaBackend()
    assert not backend.connect()
    assert backend._client is None
    assert backend._stock_data_client is None
