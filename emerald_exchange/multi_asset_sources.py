"""Bounded provider reads for dated FX and property valuation observations."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime, time
from typing import Any
from uuid import uuid4

from agent_connector_sdk.source_connectors.http_safety import safe_get_json


def _digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def _number(value: Any, *, positive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("invalid provider value")
    result = float(value)
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        raise ValueError("invalid provider value")
    return result


def _identity(tenant_id: str, source_id: str, license_tag: str) -> None:
    if not all(
        isinstance(x, str) and x.strip() for x in (tenant_id, source_id, license_tag)
    ):
        raise ValueError("tenant, source and license are required")


def read_fx(
    api_key: str,
    *,
    base: str,
    quote: str,
    tenant_id: str,
    source_id: str,
    license_tag: str,
) -> dict[str, Any]:
    """Read one FMP FX quote preserving pair direction and provider timestamp."""
    _identity(tenant_id, source_id, license_tag)
    if (
        not api_key
        or not all(
            len(x) == 3 and x.isascii() and x.isalpha() and x.isupper()
            for x in (base, quote)
        )
        or base == quote
    ):
        raise ValueError("invalid FX source configuration")
    symbol = base + quote
    payload = safe_get_json(
        "https://financialmodelingprep.com/stable/quote",
        params={"symbol": symbol},
        headers={"apikey": api_key},
        max_bytes=1024 * 1024,
        max_redirects=0,
    )
    if (
        not isinstance(payload, list)
        or len(payload) != 1
        or not isinstance(payload[0], dict)
    ):
        raise ValueError("invalid FX provider response")
    item = payload[0]
    timestamp = item.get("timestamp")
    if item.get("symbol") != symbol or type(timestamp) is not int:
        raise ValueError("invalid FX provider identity")
    observed = datetime.now(UTC)
    event = datetime.fromtimestamp(timestamp, UTC)
    if event > observed:
        raise ValueError("future provider timestamp")
    event_id = _digest([symbol, timestamp])
    record = {
        "tenant_id": tenant_id,
        "source_id": source_id,
        "provider": "financialmodelingprep",
        "instrument_id": symbol,
        "source_event_id": event_id,
        "event_time_utc": event.isoformat(),
        "observed_at_utc": observed.isoformat(),
        "license_tag": license_tag,
        "source_digest": _digest(item),
        "base_currency": base,
        "quote_currency": quote,
        "rate": _number(item.get("price"), positive=True),
    }
    return {"records": [record], "checkpoint": {"generation": uuid4().hex}}


def read_valuation(
    api_key: str,
    *,
    attom_id: int,
    tenant_id: str,
    source_id: str,
    license_tag: str,
    max_age_days: int,
) -> dict[str, Any]:
    """Read ATTOM's dated AVM without retaining address or owner data."""
    _identity(tenant_id, source_id, license_tag)
    if (
        not api_key
        or type(attom_id) is not int
        or attom_id <= 0
        or type(max_age_days) is not int
        or max_age_days < 0
    ):
        raise ValueError("invalid valuation source configuration")
    payload = safe_get_json(
        "https://api.gateway.attomdata.com/propertyapi/v1.0.0/avm/snapshot",
        params={"attomid": attom_id},
        headers={"apikey": api_key, "accept": "application/json"},
        max_bytes=2 * 1024 * 1024,
        max_redirects=0,
    )
    properties = payload.get("property") if isinstance(payload, dict) else None
    if (
        not isinstance(properties, list)
        or len(properties) != 1
        or not isinstance(properties[0], dict)
    ):
        raise ValueError("invalid valuation provider response")
    item = properties[0]
    identifier, avm = item.get("identifier"), item.get("avm")
    if (
        not isinstance(identifier, dict)
        or str(identifier.get("attomId")) != str(attom_id)
        or not isinstance(avm, dict)
    ):
        raise ValueError("invalid valuation provider identity")
    amount = avm.get("amount")
    if not isinstance(amount, dict):
        raise TypeError("invalid valuation provider amount")
    raw_date = avm.get("eventDate")
    if not isinstance(raw_date, str):
        raise TypeError("invalid valuation provider date")
    valuation = date.fromisoformat(raw_date)
    if valuation.isoformat() != raw_date:
        raise ValueError("invalid valuation provider date")
    observed = datetime.now(UTC)
    age = (observed.date() - valuation).days
    if age < 0:
        raise ValueError("future valuation date")
    event_id = _digest([attom_id, raw_date, avm.get("eventID")])
    record = {
        "tenant_id": tenant_id,
        "source_id": source_id,
        "provider": "attom",
        "instrument_id": f"attom:{attom_id}",
        "source_event_id": event_id,
        "event_time_utc": datetime.combine(valuation, time.min, UTC).isoformat(),
        "observed_at_utc": observed.isoformat(),
        "license_tag": license_tag,
        "source_digest": _digest(avm),
        "valuation_date": datetime.combine(valuation, time.min, UTC).isoformat(),
        "method": "attom_avm",
        "currency": "USD",
        "estimated_value": _number(amount.get("value"), positive=False),
        "staleness_days": age,
        "stale": age > max_age_days,
    }
    return {"records": [record], "checkpoint": {"generation": uuid4().hex}}


def read_commodity(
    api_key: str,
    *,
    dataset: str,
    symbol: str,
    start: str,
    end: str,
    tenant_id: str,
    source_id: str,
    license_tag: str,
) -> dict[str, Any]:
    """Read a specific Databento spot or outright futures trade and definition."""
    import base64
    import re

    from agent_connector_sdk.source_connectors.http_safety import safe_get_bytes

    _identity(tenant_id, source_id, license_tag)
    if (
        not api_key
        or not re.fullmatch(r"[A-Z0-9.]{1,32}", dataset)
        or not re.fullmatch(r"[A-Z0-9][A-Z0-9./_-]{0,63}", symbol)
    ):
        raise ValueError("invalid commodity source configuration")
    begin = datetime.fromisoformat(start)
    finish = datetime.fromisoformat(end)
    if (
        begin.utcoffset() is None
        or finish.utcoffset() is None
        or not 0 < (finish - begin).total_seconds() <= 86400
    ):
        raise ValueError("commodity range must be timezone-aware and at most one day")
    authorization = base64.b64encode((api_key + ":").encode()).decode()
    params = {
        "dataset": dataset,
        "symbols": symbol,
        "stype_in": "raw_symbol",
        "start": start,
        "end": end,
        "encoding": "json",
        "pretty_px": "true",
        "pretty_ts": "true",
        "map_symbols": "true",
        "limit": "1",
    }

    def fetch(schema: str) -> dict[str, Any]:
        raw, _ = safe_get_bytes(
            "https://hist.databento.com/v0/timeseries.get_range",
            params={**params, "schema": schema},
            headers={"Authorization": "Basic " + authorization},
            max_bytes=1024 * 1024,
            max_redirects=0,
        )
        lines = raw.splitlines()
        if len(lines) != 1:
            raise ValueError("commodity provider returned no single record")
        result = json.loads(lines[0])
        if not isinstance(result, dict):
            raise TypeError("invalid commodity provider response")
        return result

    definition = fetch("definition")
    trade = fetch("trades")
    definition_header, trade_header = definition.get("hd"), trade.get("hd")
    if not isinstance(definition_header, dict) or not isinstance(trade_header, dict):
        raise TypeError("invalid commodity provider headers")
    if (
        definition.get("raw_symbol") != symbol
        or trade.get("symbol") != symbol
        or type(definition_header.get("instrument_id")) is not int
        or type(definition_header.get("publisher_id")) is not int
        or definition_header.get("instrument_id") != trade_header.get("instrument_id")
        or definition_header.get("publisher_id") != trade_header.get("publisher_id")
    ):
        raise ValueError("commodity instrument mismatch")
    if definition.get("security_update_action") == "D":
        raise ValueError("commodity definition was deleted")
    if definition.get("instrument_class") not in {"F", "Y"}:
        raise ValueError("unsupported commodity instrument")
    event_time = trade_header.get("ts_event")
    if not isinstance(event_time, str):
        raise TypeError("invalid commodity event time")
    event = datetime.fromisoformat(event_time)
    if event.utcoffset() is None or not begin <= event < finish:
        raise ValueError("commodity event outside requested range")
    definition_time = definition_header.get("ts_event")
    if not isinstance(definition_time, str):
        raise TypeError("invalid commodity definition time")
    definition_event = datetime.fromisoformat(definition_time)
    if definition_event.utcoffset() is None or definition_event > event:
        raise ValueError("commodity definition follows trade")
    currency = definition.get("currency")
    if (
        not isinstance(currency, str)
        or len(currency) != 3
        or not currency.isascii()
        or not currency.isalpha()
        or not currency.isupper()
    ):
        raise ValueError("invalid commodity currency")
    raw_price = trade.get("price")
    if not isinstance(raw_price, str):
        raise TypeError("invalid commodity price")
    price = _number(float(raw_price), positive=True)
    observed = datetime.now(UTC)
    event_id = _digest([dataset, trade_header, trade.get("sequence")])
    record: dict[str, Any] = {
        "tenant_id": tenant_id,
        "source_id": source_id,
        "provider": "databento",
        "instrument_id": f"{dataset}:{symbol}",
        "source_event_id": event_id,
        "event_time_utc": event.isoformat(),
        "observed_at_utc": observed.isoformat(),
        "license_tag": license_tag,
        "source_digest": _digest([definition, trade]),
        "currency": currency,
        "price": price,
    }
    if definition["instrument_class"] == "F":
        expiry = definition.get("expiration")
        if not isinstance(expiry, str):
            raise ValueError("futures expiry is missing")
        expires = datetime.fromisoformat(expiry)
        if expires.utcoffset() is None or expires < event:
            raise ValueError("invalid futures expiry")
        record.update(
            basis="future",
            contract_code=symbol,
            expiry=expires.isoformat(),
            roll_rule="none:fixed-contract",
        )
    else:
        record["basis"] = "spot"
    return {"records": [record], "checkpoint": {"generation": uuid4().hex}}


def read_gold_spot(
    api_key: str, *, tenant_id: str, source_id: str, license_tag: str
) -> dict[str, Any]:
    """Read Twelve Data's gold spot quote using its last minute timestamp."""
    _identity(tenant_id, source_id, license_tag)
    if not api_key:
        raise ValueError("spot source requires an API key")
    payload = safe_get_json(
        "https://api.twelvedata.com/quote",
        params={"symbol": "XAU/USD", "interval": "1min"},
        headers={"Authorization": "apikey " + api_key},
        max_bytes=1024 * 1024,
        max_redirects=0,
    )
    if not isinstance(payload, dict) or payload.get("symbol") != "XAU/USD":
        raise ValueError("invalid spot provider identity")
    timestamp = payload.get("last_quote_at")
    raw_price = payload.get("close")
    if type(timestamp) is not int or not isinstance(raw_price, str):
        raise ValueError("invalid spot provider quote")
    event = datetime.fromtimestamp(timestamp, UTC)
    observed = datetime.now(UTC)
    if event > observed:
        raise ValueError("future spot provider time")
    record = {
        "tenant_id": tenant_id,
        "source_id": source_id,
        "provider": "twelvedata",
        "instrument_id": "XAU/USD",
        "source_event_id": _digest(["XAU/USD", timestamp]),
        "event_time_utc": event.isoformat(),
        "observed_at_utc": observed.isoformat(),
        "license_tag": license_tag,
        "source_digest": _digest(payload),
        "basis": "spot",
        "currency": "USD",
        "price": _number(float(raw_price), positive=True),
    }
    return {"records": [record], "checkpoint": {"generation": uuid4().hex}}
