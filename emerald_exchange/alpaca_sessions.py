"""Classify one-minute stock bars using Alpaca's exchange calendar.

Classification describes the start of a full minute, not entitlement to trade
or the completeness of any market-data feed. Half days have no post-market
session under Alpaca's published schedule. Overnight data is left unclassified.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from emerald_exchange.alpaca_stock_history import _instant

_EASTERN = ZoneInfo("America/New_York")


def classify_stock_bar_sessions(
    client: Any, bars: list[dict[str, Any]], *, feed: str, timeframe: str
) -> None:
    """Add calendar-backed session labels in place, refusing ambiguous bars."""
    if feed not in {"iex", "sip"} or timeframe != "1Min":
        raise ValueError("session classification requires one-minute IEX or SIP bars")
    if not bars:
        return
    local_times: list[datetime] = []
    for bar in bars:
        text, ticks = _instant(bar["timestamp"])
        if ticks % 60_000_000_000:
            raise ValueError("stock bar does not start on a minute boundary")
        local_times.append(datetime.fromisoformat(text).astimezone(_EASTERN))
    start, end = min(t.date() for t in local_times), max(t.date() for t in local_times)
    if (end - start).days > 366 or start < date(1970, 1, 1) or end > date(2029, 12, 31):
        raise ValueError("calendar interval is unsupported")
    from alpaca.trading.requests import GetCalendarRequest

    days = client.get_calendar(GetCalendarRequest(start=start, end=end))
    if not isinstance(days, list):
        raise TypeError("invalid exchange calendar")
    calendar = {}
    for day in days:
        if (
            not isinstance(day.date, date)
            or not isinstance(day.open, datetime)
            or not isinstance(day.close, datetime)
        ):
            raise TypeError("invalid exchange calendar")
        if (
            day.date in calendar
            or not start <= day.date <= end
            or day.open.tzinfo is not None
            or day.close.tzinfo is not None
        ):
            raise ValueError("invalid exchange calendar")
        if (
            day.open.date() != day.date
            or day.close.date() != day.date
            or not time(4) <= day.open.time() < day.close.time() <= time(16)
        ):
            raise ValueError("invalid exchange calendar")
        calendar[day.date] = (day.open.time(), day.close.time())
    labels = []
    for local in local_times:
        day = calendar.get(local.date())
        now = local.time().replace(tzinfo=None)
        if day is None:
            labels.append("outside_session")
        elif time(4) <= now < day[0]:
            labels.append("pre_market")
        elif day[0] <= now < day[1]:
            labels.append("regular")
        elif day[1] == time(16) and day[1] <= now < time(20):
            labels.append("post_market")
        else:
            labels.append("outside_session")
    for bar, label in zip(bars, labels, strict=True):
        bar["session_scope"] = "alpaca_calendar"
        bar["session"] = label
