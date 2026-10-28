"""Bounded CCXT OHLCV pages with explicit windows and advancing cursors."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from emerald_exchange.alpaca_stock_history import _instant, _number

_SYMBOL = re.compile(
    r"^[A-Z0-9][A-Z0-9.\-]{0,19}/[A-Z0-9][A-Z0-9.\-]{0,19}(?::[A-Z0-9.\-]{1,20})?$"
)
_INTERVALS = frozenset({"1m", "5m", "1h", "1d"})


def read_history_page(
    exchange: Any,
    *,
    exchange_id: str,
    symbol: str,
    start: str,
    end: str,
    interval: str,
    license_tag: str,
    limit: int,
    page_token: str | None,
) -> dict[str, Any]:
    if (
        not isinstance(symbol, str)
        or not _SYMBOL.fullmatch(symbol)
        or interval not in _INTERVALS
    ):
        raise ValueError("invalid exchange symbol or interval")
    if (
        not isinstance(license_tag, str)
        or not license_tag.strip()
        or type(limit) is not int
        or not 1 <= limit <= 1000
    ):
        raise ValueError("invalid exchange source parameters")
    _, start_ns = _instant(start)
    _, end_ns = _instant(end)
    if start_ns < 0 or start_ns % 1_000_000 or end_ns % 1_000_000 or start_ns >= end_ns:
        raise ValueError("exchange interval requires increasing millisecond bounds")
    first, last = start_ns // 1_000_000, end_ns // 1_000_000
    if page_token is None:
        cursor = first
    elif (
        not isinstance(page_token, str)
        or not page_token.isascii()
        or not page_token.isdecimal()
        or len(page_token) > 16
        or str(int(page_token)) != page_token
    ):
        raise ValueError("invalid exchange continuation")
    else:
        cursor = int(page_token)
        if not first <= cursor < last:
            raise ValueError("exchange continuation outside window")
    if exchange is None:
        raise RuntimeError("exchange is not connected")
    page = exchange.fetch_ohlcv(symbol, interval, since=cursor, limit=limit)
    if not isinstance(page, list) or len(page) > limit:
        raise ValueError("invalid exchange page")
    records, previous = [], cursor - 1
    reached_end = False
    for row in page:
        if (
            not isinstance(row, (list, tuple))
            or len(row) != 6
            or type(row[0]) is not int
            or row[0] < cursor
            or row[0] <= previous
        ):
            raise ValueError("invalid exchange candle identity")
        previous = row[0]
        if previous >= last:
            reached_end = True
            continue
        open_, high, low, close, volume = (_number(value) for value in row[1:])
        if high < max(open_, low, close) or low > min(open_, high, close):
            raise ValueError("invalid exchange candle bounds")
        timestamp = (
            (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=previous))
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        identity = hashlib.sha256(
            json.dumps(
                [exchange_id, symbol, interval, previous], separators=(",", ":")
            ).encode()
        ).hexdigest()
        records.append(
            {
                "candle_id": identity,
                "exchange": exchange_id,
                "symbol": symbol,
                "interval": interval,
                "timestamp": timestamp,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "license_tag": license_tag,
            }
        )
    token = (
        str(previous + 1) if page and not reached_end and previous + 1 < last else None
    )
    return {
        "candles": records,
        "next_page_token": token,
        "checkpoint": {"cursor": token, "generation": uuid4().hex},
    }
