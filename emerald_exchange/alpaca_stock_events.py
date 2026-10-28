"""Bounded Alpaca news and dividend reads with provider identities."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID, uuid4

from emerald_exchange.alpaca_stock_history import _SYMBOL, _instant, _number


def _request(
    symbol: str, license_tag: str, limit: int, max_limit: int, page_token: str | None
) -> None:
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("invalid stock symbol")
    if not isinstance(license_tag, str) or not license_tag.strip():
        raise ValueError("stock data requires a license tag")
    if type(limit) is not int or not 1 <= limit <= max_limit:
        raise ValueError("invalid stock page size")
    if page_token is not None and (
        not isinstance(page_token, str) or not page_token or len(page_token) > 4096
    ):
        raise ValueError("invalid stock page token")


def _page(response: Any, page_token: str | None) -> str | None:
    if not isinstance(response, dict) or "next_page_token" not in response:
        raise ValueError("invalid stock event page")
    token = response["next_page_token"]
    if token is not None and (
        not isinstance(token, str)
        or not token
        or len(token) > 4096
        or token == page_token
    ):
        raise ValueError("invalid stock event continuation")
    return token


def read_news_page(
    client: Any,
    *,
    symbol: str,
    start: str,
    end: str,
    license_tag: str,
    limit: int,
    page_token: str | None,
) -> dict[str, Any]:
    """Fetch headline metadata; provider article content is not requested."""
    _request(symbol, license_tag, limit, 50, page_token)
    start_text, first = _instant(start)
    end_text, last = _instant(end)
    if first >= last:
        raise ValueError("news interval must increase")
    params = {
        "symbols": symbol,
        "start": start_text,
        "end": end_text,
        "sort": "asc",
        "limit": limit,
        "include_content": False,
    }
    if page_token is not None:
        params["page_token"] = page_token
    response = client.get("/news", data=params)
    token = _page(response, page_token)
    news = response.get("news")
    if (
        not isinstance(news, list)
        or len(news) > limit
        or (not news and token is not None)
    ):
        raise ValueError("invalid news page")
    records = []
    ids = set()
    for item in news:
        if (
            not isinstance(item, dict)
            or type(item.get("id")) is not int
            or item["id"] < 0
        ):
            raise ValueError("invalid news identity")
        headline, author, source, symbols = (
            item.get(key) for key in ("headline", "author", "source", "symbols")
        )
        if (
            any(
                not isinstance(value, str) or not value.strip()
                for value in (headline, author, source)
            )
            or not isinstance(symbols, list)
            or symbol not in symbols
            or any(not isinstance(s, str) or not _SYMBOL.fullmatch(s) for s in symbols)
        ):
            raise ValueError("invalid news metadata")
        created, created_ticks = _instant(item.get("created_at"))
        updated, updated_ticks = _instant(item.get("updated_at"))
        if (
            created_ticks > updated_ticks
            or not first <= updated_ticks <= last
            or item["id"] in ids
        ):
            raise ValueError("invalid news timestamp or duplicate identity")
        ids.add(item["id"])
        records.append(
            {
                "news_id": str(item["id"]),
                "symbol": symbol,
                "headline": headline,
                "author": author,
                "source": source,
                "created_at": created,
                "updated_at": updated,
                "license_tag": license_tag,
            }
        )
    return {
        "news": records,
        "next_page_token": token,
        "checkpoint": {"cursor": token, "generation": uuid4().hex},
    }


def _date(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("invalid corporate action date")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid corporate action date") from None
    if result.isoformat() != value:
        raise ValueError("invalid corporate action date")
    return value


def read_dividends_page(
    client: Any,
    *,
    symbol: str,
    start: str,
    end: str,
    license_tag: str,
    limit: int,
    page_token: str | None,
) -> dict[str, Any]:
    """Read complete corporate action records; provider may publish them late."""
    _request(symbol, license_tag, limit, 1000, page_token)
    first, last = _date(start), _date(end)
    if first > last:
        raise ValueError("dividend interval must increase")
    params = {
        "symbols": symbol,
        "start": first,
        "end": last,
        "types": "cash_dividend,stock_dividend",
        "data_quality": "complete",
        "sort": "asc",
        "limit": limit,
    }
    if page_token is not None:
        params["page_token"] = page_token
    response = client.get("/corporate-actions", data=params)
    token = _page(response, page_token)
    groups = response.get("corporate_actions")
    if not isinstance(groups, dict) or any(
        values not in (None, [])
        for key, values in groups.items()
        if key not in {"cash_dividends", "stock_dividends"}
    ):
        raise ValueError("invalid dividend page")
    records = []
    ids = set()
    for key, kind in (("cash_dividends", "cash"), ("stock_dividends", "stock")):
        items = groups.get(key, [])
        if not isinstance(items, list):
            raise TypeError("invalid dividend page")
        for item in items:
            if not isinstance(item, dict) or item.get("symbol") != symbol:
                raise ValueError("invalid dividend record")
            try:
                identity = str(UUID(item["id"]))
                process_date = _date(item["process_date"])
                ex_date = _date(item["ex_date"])
                rate = _number(item["rate"])
            except (KeyError, ValueError, TypeError, AttributeError):
                raise ValueError("invalid dividend record") from None
            if not first <= process_date <= last or identity in ids:
                raise ValueError("invalid dividend identity or date")
            ids.add(identity)
            record = {
                "dividend_id": identity,
                "symbol": symbol,
                "kind": kind,
                "rate": rate,
                "process_date": process_date,
                "ex_date": ex_date,
                "license_tag": license_tag,
            }
            for field in ("record_date", "payable_date"):
                if item.get(field) is not None:
                    record[field] = _date(item[field])
            records.append(record)
    if len(records) > limit or (not records and token is not None):
        raise ValueError("invalid dividend page")
    return {
        "dividends": records,
        "next_page_token": token,
        "checkpoint": {"cursor": token, "generation": uuid4().hex},
    }
