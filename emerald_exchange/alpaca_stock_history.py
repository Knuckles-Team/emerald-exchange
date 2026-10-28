"""One bounded, explicitly labeled page from Alpaca stock market data."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_TIMEFRAME = re.compile(
    r"^(?:[1-9]|[1-5][0-9])Min$|^(?:[1-9]|1[0-9]|2[0-3])Hour$|^1(?:Day|Week)$|^(?:1|2|3|4|6|12)Month$"
)
_ADJUSTMENTS = frozenset({"raw", "split", "dividend", "spin-off", "all"})
_FEEDS = frozenset({"iex", "sip", "otc", "boats"})
_MAX_PAGE_SIZE = 10000


_TIMESTAMP = re.compile(
    r"^(?P<seconds>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d{1,9}))?(?P<zone>Z|[+-]\d{2}:\d{2})$"
)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _instant(value: str) -> tuple[str, int]:
    """Canonical UTC text and integer nanoseconds, without losing precision."""
    if not isinstance(value, str) or not (match := _TIMESTAMP.fullmatch(value)):
        raise ValueError("stock data needs an explicit RFC 3339 timestamp")
    try:
        zone = "+00:00" if match["zone"] == "Z" else match["zone"]
        base = datetime.fromisoformat(match["seconds"] + zone).astimezone(UTC)
        fraction = (match["fraction"] or "").ljust(9, "0")
        delta = base - _EPOCH
        ticks = (delta.days * 86400 + delta.seconds) * 1_000_000_000 + int(fraction)
        return base.isoformat(timespec="seconds").replace(
            "+00:00", ""
        ) + "." + fraction + "Z", ticks
    except (ValueError, OverflowError):
        raise ValueError("stock data needs a valid RFC 3339 timestamp") from None


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("invalid stock bar values")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid stock bar values")
    return number


def _bar(
    raw: Any,
    *,
    symbol: str,
    timeframe: str,
    adjustment: str,
    feed: str,
    license_tag: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("invalid stock bar")
    timestamp, stamp = _instant(raw.get("t"))
    if not start <= stamp <= end:
        raise ValueError("stock bar lies outside the requested interval")
    try:
        open_, high, low, close, volume = (
            _number(raw[k]) for k in ("o", "h", "l", "c", "v")
        )
    except KeyError:
        raise ValueError("stock bar is missing a required value") from None
    if high < max(open_, low, close) or low > min(open_, high, close):
        raise ValueError("stock bar price bounds are invalid")
    identity = json.dumps(
        [symbol, timeframe, adjustment, feed, timestamp], separators=(",", ":")
    ).encode()
    return {
        "bar_id": hashlib.sha256(identity).hexdigest(),
        "symbol": symbol,
        "timestamp": timestamp,
        "timeframe": timeframe,
        "adjustment": adjustment,
        "feed": feed,
        "session_scope": "feed_native",
        "license_tag": license_tag,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def read_stock_bars_page(
    client: Any,
    *,
    symbol: str,
    start: str,
    end: str,
    timeframe: str,
    adjustment: str,
    feed: str,
    license_tag: str,
    limit: int,
    page_token: str | None,
) -> dict[str, Any]:
    """Read one provider page; never claim a partial window is complete."""
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("invalid stock symbol")
    if not isinstance(timeframe, str) or not _TIMEFRAME.fullmatch(timeframe):
        raise ValueError("invalid stock timeframe")
    if adjustment not in _ADJUSTMENTS or feed not in _FEEDS:
        raise ValueError("invalid stock adjustment or feed")
    if not isinstance(license_tag, str) or not license_tag.strip():
        raise ValueError("stock bars require a license tag")
    if type(limit) is not int or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise ValueError("invalid stock page size")
    if page_token is not None and (
        not isinstance(page_token, str) or not page_token or len(page_token) > 4096
    ):
        raise ValueError("invalid stock page token")
    start_text, start_time = _instant(start)
    end_text, end_time = _instant(end)
    if start_time >= end_time:
        raise ValueError("stock interval must increase")
    params = {
        "symbols": symbol,
        "start": start_text,
        "end": end_text,
        "timeframe": timeframe,
        "adjustment": adjustment,
        "feed": feed,
        "limit": limit,
        "sort": "asc",
        "currency": "USD",
    }
    if page_token is not None:
        params["page_token"] = page_token
    response = client.get("/stocks/bars", data=params)
    if not isinstance(response, dict) or "next_page_token" not in response:
        raise ValueError("invalid stock page")
    bars = response.get("bars")
    if not isinstance(bars, dict) or set(bars) - {symbol}:
        raise ValueError("invalid stock page symbols")
    page = bars.get(symbol, [])
    if not isinstance(page, list) or len(page) > limit:
        raise ValueError("invalid stock bar array")
    next_token = response["next_page_token"]
    if next_token is not None and (
        not isinstance(next_token, str)
        or not next_token
        or len(next_token) > 4096
        or next_token == page_token
    ):
        raise ValueError("invalid stock continuation")
    if not page and next_token is not None:
        raise ValueError("empty stock page has a continuation")
    records = [
        _bar(
            raw,
            symbol=symbol,
            timeframe=timeframe,
            adjustment=adjustment,
            feed=feed,
            license_tag=license_tag,
            start=start_time,
            end=end_time,
        )
        for raw in page
    ]
    stamps = [record["timestamp"] for record in records]
    if stamps != sorted(set(stamps)):
        raise ValueError("stock bar timestamps must strictly increase")
    return {
        "bars": records,
        "next_page_token": next_token,
        "has_more": next_token is not None,
        "checkpoint": {"cursor": next_token, "generation": uuid4().hex},
    }


_QUOTE_FEEDS = _FEEDS | frozenset({"delayed_sip", "overnight"})


def read_stock_quote(
    client: Any, *, symbol: str, feed: str, license_tag: str
) -> dict[str, Any]:
    """Read a provider quote without fabricating a trade price or volume."""
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("invalid stock symbol")
    if feed not in _QUOTE_FEEDS:
        raise ValueError("invalid quote feed")
    if not isinstance(license_tag, str) or not license_tag.strip():
        raise ValueError("stock quotes require a license tag")
    response = client.get(
        "/stocks/quotes/latest",
        data={"symbols": symbol, "feed": feed, "currency": "USD"},
    )
    if not isinstance(response, dict) or not isinstance(response.get("quotes"), dict):
        raise TypeError("invalid stock quote response")
    quotes = response["quotes"]
    if set(quotes) != {symbol} or not isinstance(quotes[symbol], dict):
        raise ValueError("requested stock quote is unavailable")
    raw = quotes[symbol]
    timestamp, _ = _instant(raw.get("t"))
    try:
        bid, ask = _number(raw["bp"]), _number(raw["ap"])
        bid_size, ask_size = raw["bs"], raw["as"]
        bid_exchange, ask_exchange = raw["bx"], raw["ax"]
        conditions, tape = raw["c"], raw["z"]
    except KeyError:
        raise ValueError("stock quote is missing a required value") from None
    if (
        type(bid_size) is not int
        or bid_size < 0
        or type(ask_size) is not int
        or ask_size < 0
        or not isinstance(bid_exchange, str)
        or not isinstance(ask_exchange, str)
        or tape not in {"A", "B", "C", "N", "O"}
        or not isinstance(conditions, list)
        or any(not isinstance(item, str) for item in conditions)
    ):
        raise ValueError("invalid stock quote metadata")
    identity = json.dumps(
        [
            symbol,
            feed,
            timestamp,
            bid,
            ask,
            bid_size,
            ask_size,
            bid_exchange,
            ask_exchange,
            conditions,
            tape,
        ],
        separators=(",", ":"),
    ).encode()
    quote = {
        "quote_id": hashlib.sha256(identity).hexdigest(),
        "symbol": symbol,
        "timestamp": timestamp,
        "feed": feed,
        "session_scope": "feed_native",
        "license_tag": license_tag,
        "bid": bid,
        "ask": ask,
        "bid_size": bid_size,
        "ask_size": ask_size,
        "bid_exchange": bid_exchange,
        "ask_exchange": ask_exchange,
        "conditions": conditions,
        "conditions_json": json.dumps(conditions, separators=(",", ":")),
        "tape": tape,
    }
    return {"quotes": [quote], "checkpoint": {"generation": uuid4().hex}}
