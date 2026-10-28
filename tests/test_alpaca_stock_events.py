"""Alpaca news and dividend fixtures preserve identities and bounded pages."""

import pytest

from emerald_exchange.backends import AlpacaBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations


NEWS = {
    "id": 123,
    "headline": "A headline",
    "author": "A reporter",
    "source": "wire",
    "symbols": ["AAPL"],
    "created_at": "2026-01-02T14:30:00Z",
    "updated_at": "2026-01-02T14:31:00.123456789Z",
}
DIVIDEND = {
    "id": "11cfd108-292e-4cc6-bfbf-5999cdbc4029",
    "symbol": "AAPL",
    "rate": 0.125,
    "process_date": "2026-01-02",
    "ex_date": "2026-01-01",
    "payable_date": "2026-01-03",
}


class Page:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, path, data):
        self.calls.append((path, data))
        return self.response


def operations(response, *, dividend=False):
    backend = AlpacaBackend()
    page = Page(response)
    if dividend:
        backend._corporate_actions_client = page
    else:
        backend._news_client = page
    return ExchangeReadOperations(backend), page


def test_news_page_keeps_source_and_precision_without_fetching_content():
    ops, page = operations({"news": [NEWS], "next_page_token": "next"})
    result = ops.get_stock_news(
        "AAPL", "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z", "licensed", "delta"
    )
    assert result["news"][0]["updated_at"] == "2026-01-02T14:31:00.123456789Z"
    assert result["news"][0]["news_id"] == "123"
    assert page.calls[0][0] == "/news"
    assert page.calls[0][1]["include_content"] is False
    assert result["checkpoint"]["cursor"] == "next"


def test_dividend_page_preserves_dates_and_rates():
    ops, page = operations(
        {"corporate_actions": {"cash_dividends": [DIVIDEND]}, "next_page_token": None},
        dividend=True,
    )
    result = ops.get_stock_dividends(
        "AAPL", "2026-01-01", "2026-01-31", "licensed", "delta"
    )
    assert result["dividends"][0]["rate"] == 0.125
    assert result["dividends"][0]["ex_date"] == "2026-01-01"
    assert page.calls[0][0] == "/corporate-actions"
    assert page.calls[0][1]["data_quality"] == "complete"


def test_empty_unrequested_corporate_action_group_is_allowed():
    ops, _ = operations(
        {
            "corporate_actions": {"reverse_splits": [], "stock_dividends": []},
            "next_page_token": None,
        },
        dividend=True,
    )
    assert not ops.get_stock_dividends(
        "AAPL", "2026-01-01", "2026-01-31", "licensed", "delta"
    )["dividends"]


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"news": [NEWS, NEWS], "next_page_token": None},
        {"news": [{**NEWS, "updated_at": "secret"}], "next_page_token": None},
        {"news": [], "next_page_token": "next"},
    ],
)
def test_bad_news_page_is_redacted(response):
    ops, _ = operations(response)
    with pytest.raises(RuntimeError, match="news read failed") as error:
        ops.get_stock_news(
            "AAPL", "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z", "licensed", "delta"
        )
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        {},
        {
            "corporate_actions": {"cash_dividends": [DIVIDEND, DIVIDEND]},
            "next_page_token": None,
        },
        {
            "corporate_actions": {"cash_dividends": [{**DIVIDEND, "rate": 10**1000}]},
            "next_page_token": None,
        },
        {"corporate_actions": {}, "next_page_token": "next"},
    ],
)
def test_bad_dividend_page_is_redacted(response):
    ops, _ = operations(response, dividend=True)
    with pytest.raises(RuntimeError, match="corporate actions read failed"):
        ops.get_stock_dividends("AAPL", "2026-01-01", "2026-01-31", "licensed", "delta")
