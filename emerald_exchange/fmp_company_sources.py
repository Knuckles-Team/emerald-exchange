"""Bounded FMP profile, fundamentals, earnings and logo source records."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from agent_connector_sdk.source_connectors.http_safety import (
    safe_get_bytes,
    safe_get_json,
)

from emerald_exchange.alpaca_stock_history import _SYMBOL

_BASE = "https://financialmodelingprep.com/stable/"
_IMAGE = "https://images.financialmodelingprep.com/symbol/"


def _date(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("invalid provider date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("invalid provider date")
    return value


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("invalid provider numeric value")
    try:
        result = float(value)
    except OverflowError:
        raise ValueError("invalid provider numeric value") from None
    if not math.isfinite(result):
        raise ValueError("invalid provider numeric value")
    return result


def _request(api_key: str, endpoint: str, symbol: str) -> Any:
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("company source requires an FMP API key")
    return safe_get_json(
        _BASE + endpoint,
        params={"symbol": symbol},
        headers={"apikey": api_key},
        max_bytes=2 * 1024 * 1024,
        max_redirects=0,
    )


def read_company_records(
    api_key: str, *, symbol: str, dataset: str, license_tag: str
) -> dict[str, Any]:
    """Read a bounded provider snapshot. No completeness or redistribution claim."""
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("invalid company symbol")
    if not isinstance(license_tag, str) or not license_tag.strip():
        raise ValueError("company source requires a license tag")
    if dataset not in {"profile", "income", "earnings", "logo"}:
        raise ValueError("invalid company dataset")
    endpoint = {
        "profile": "profile",
        "income": "income-statement",
        "earnings": "earnings",
        "logo": "profile",
    }[dataset]
    items = _request(api_key, endpoint, symbol)
    if not isinstance(items, list) or len(items) > 1000:
        raise ValueError("invalid company response")
    if dataset in {"profile", "logo"} and len(items) != 1:
        raise ValueError("company profile is unavailable or ambiguous")
    now = datetime.now(UTC).isoformat()
    records = []
    identities = set()
    for item in items:
        if not isinstance(item, dict) or item.get("symbol") != symbol:
            raise ValueError("invalid company record")
        record: dict[str, Any] = {
            "symbol": symbol,
            "dataset": dataset,
            "provider": "financialmodelingprep",
            "observed_at": now,
            "license_tag": license_tag,
        }
        if dataset in {"profile", "logo"}:
            name = item.get("companyName")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("company name is missing")
            record["company_name"] = name
            identity = symbol
            if dataset == "profile":
                for key, output in (
                    ("industry", "industry"),
                    ("sector", "sector"),
                    ("exchange", "exchange"),
                    ("currency", "currency"),
                ):
                    value = item.get(key)
                    if value is not None:
                        if not isinstance(value, str):
                            raise TypeError("invalid company profile")
                        record[output] = value
            else:
                expected_url = _IMAGE + symbol + ".png"
                if (
                    item.get("defaultImage") is not False
                    or item.get("image") != expected_url
                ):
                    raise ValueError("company logo is unavailable")
                image, _encoding = safe_get_bytes(
                    expected_url, max_bytes=1024 * 1024, max_redirects=0
                )
                if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("invalid company logo")
                record["image_base64"] = base64.b64encode(image).decode("ascii")
                record["image_sha256"] = hashlib.sha256(image).hexdigest()
                record["image_media_type"] = "image/png"
        elif dataset == "income":
            period_date = _date(item.get("date"))
            period = item.get("period")
            currency = item.get("reportedCurrency")
            if (
                period not in {"FY", "Q1", "Q2", "Q3", "Q4"}
                or not isinstance(currency, str)
                or len(currency) != 3
                or not currency.isascii()
                or not currency.isalpha()
                or not currency.isupper()
            ):
                raise ValueError("invalid income statement metadata")
            record.update(
                period_date=period_date,
                period=period,
                currency=currency,
                revenue=_finite(item.get("revenue")),
                net_income=_finite(item.get("netIncome")),
            )
            if item.get("filingDate") is not None:
                record["filing_date"] = _date(item["filingDate"])
            identity = f"{symbol}:{period_date}:{period}"
        else:
            announcement_date = _date(item.get("date"))
            record["announcement_date"] = announcement_date
            if item.get("lastUpdated") is not None:
                record["updated_date"] = _date(item["lastUpdated"])
            for key, output in (
                ("epsActual", "eps_actual"),
                ("epsEstimated", "eps_estimated"),
                ("revenueActual", "revenue_actual"),
                ("revenueEstimated", "revenue_estimated"),
            ):
                if item.get(key) is not None:
                    record[output] = _finite(item[key])
            identity = f"{symbol}:{announcement_date}"
        record["record_id"] = hashlib.sha256(
            json.dumps([dataset, identity], separators=(",", ":")).encode()
        ).hexdigest()
        if record["record_id"] in identities:
            raise ValueError("duplicate company record")
        identities.add(record["record_id"])
        records.append(record)
    return {"records": records, "checkpoint": {"generation": uuid4().hex}}
