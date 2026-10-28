"""Provider fixtures exercise FX, futures, spot, and dated property reads."""

import json
from datetime import UTC, datetime

import pytest

from emerald_exchange import multi_asset_sources as sources
from emerald_exchange.backends import PaperBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations

IDENTITY = {"tenant_id": "tenant", "source_id": "source", "license_tag": "test-license"}


def test_fx_and_dated_valuation_provider_reads(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if "financialmodelingprep" in url:
            return [{"symbol": "EURUSD", "price": 1.12, "timestamp": 1704067200}]
        if "twelvedata" in url:
            return {
                "symbol": "XAU/USD",
                "last_quote_at": 1704067200,
                "close": "2020.25",
            }
        return {
            "property": [
                {
                    "identifier": {"attomId": 123},
                    "avm": {
                        "eventDate": "2024-01-01",
                        "eventID": 4,
                        "amount": {"value": 500000},
                    },
                }
            ]
        }

    monkeypatch.setattr(sources, "safe_get_json", get)
    monkeypatch.setenv("FMP_API_KEY", "fmp-secret")
    monkeypatch.setenv("ATTOM_API_KEY", "attom-secret")
    ops = ExchangeReadOperations(PaperBackend())
    fx = ops.get_multi_asset_records(
        "fx", **IDENTITY, mode="delta", base="EUR", quote="USD"
    )["records"][0]
    valuation = ops.get_multi_asset_records(
        "real_estate", **IDENTITY, mode="delta", attom_id=123, max_age_days=30
    )["records"][0]
    assert (fx["base_currency"], fx["quote_currency"], fx["rate"]) == (
        "EUR",
        "USD",
        1.12,
    )
    assert valuation["valuation_date"].startswith("2024-01-01")
    assert (
        valuation["staleness_days"]
        == (datetime.now(UTC).date() - datetime(2024, 1, 1, tzinfo=UTC).date()).days
    )
    assert valuation["stale"] is True
    assert all(call[1]["max_redirects"] == 0 for call in calls)
    assert all("secret" not in call[0] for call in calls)
    assert "address" not in valuation


@pytest.mark.parametrize("kind", ["F", "Y"])
def test_databento_trade_matches_definition(monkeypatch, kind):
    from agent_connector_sdk.source_connectors import http_safety

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        header = {
            "instrument_id": 42,
            "publisher_id": 1,
            "ts_event": "2024-01-01T01:00:00.000000000Z",
        }
        if kwargs["params"]["schema"] == "definition":
            item = {
                "hd": header,
                "raw_symbol": "GCZ4",
                "instrument_class": kind,
                "currency": "USD",
                "expiration": "2024-12-01T00:00:00Z",
            }
        else:
            item = {"hd": header, "symbol": "GCZ4", "price": "2000.0", "sequence": 1}
        return json.dumps(item).encode(), None

    monkeypatch.setattr(http_safety, "safe_get_bytes", get)
    result = sources.read_commodity(
        "secret",
        dataset="GLBX.MDP3",
        symbol="GCZ4",
        start="2024-01-01T00:00:00Z",
        end="2024-01-02T00:00:00Z",
        **IDENTITY,
    )["records"][0]
    assert result["price"] == 2000
    assert result["basis"] == ("future" if kind == "F" else "spot")
    if kind == "F":
        assert result["contract_code"] == "GCZ4"
        assert result["roll_rule"] == "none:fixed-contract"
    else:
        assert "expiry" not in result
    assert len(calls) == 2 and all(c[1]["max_redirects"] == 0 for c in calls)


def stub_providers(monkeypatch):
    from agent_connector_sdk.source_connectors import http_safety

    monkeypatch.setenv("FMP_API_KEY", "fmp-test-key")
    monkeypatch.setenv("ATTOM_API_KEY", "attom-test-key")
    monkeypatch.setenv("DATABENTO_API_KEY", "databento-test-key")
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "spot-test-key")

    def get_json(url, **kwargs):
        if "financialmodelingprep" in url:
            return [{"symbol": "EURUSD", "price": 1.12, "timestamp": 1704067200}]
        if "twelvedata" in url:
            return {
                "symbol": "XAU/USD",
                "last_quote_at": 1704067200,
                "close": "2020.25",
            }
        return {
            "property": [
                {
                    "identifier": {"attomId": 123},
                    "avm": {
                        "eventDate": "2024-01-01",
                        "eventID": 4,
                        "amount": {"value": 500000},
                    },
                }
            ]
        }

    def get_bytes(url, **kwargs):
        header = {
            "instrument_id": 42,
            "publisher_id": 1,
            "ts_event": "2024-01-01T01:00:00Z",
        }
        if kwargs["params"]["schema"] == "definition":
            value = {
                "hd": header,
                "raw_symbol": "GCZ4",
                "instrument_class": "F",
                "currency": "USD",
                "expiration": "2024-12-01T00:00:00Z",
            }
        else:
            value = {"hd": header, "symbol": "GCZ4", "price": "2000.0", "sequence": 1}
        return json.dumps(value).encode(), None

    monkeypatch.setattr(sources, "safe_get_json", get_json)
    monkeypatch.setattr(http_safety, "safe_get_bytes", get_bytes)


def test_invalid_provider_responses_are_redacted(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp")
    monkeypatch.setattr(
        sources,
        "safe_get_json",
        lambda *_a, **_kw: [{"symbol": "USDEUR", "price": 1, "timestamp": 1704067200}],
    )
    ops = ExchangeReadOperations(PaperBackend())
    with pytest.raises(RuntimeError, match="multi-asset provider read failed") as error:
        ops.get_multi_asset_records(
            "fx", **IDENTITY, mode="delta", base="EUR", quote="USD"
        )
    assert "secret-fmp" not in str(error.value)
    with pytest.raises(ValueError, match="requires delta"):
        ops.get_multi_asset_records("fx", **IDENTITY, mode="full")


def test_wrong_contract_or_missing_expiry_is_refused(monkeypatch):
    from agent_connector_sdk.source_connectors import http_safety

    def get(_url, **kwargs):
        header = {
            "instrument_id": 42,
            "publisher_id": 1,
            "ts_event": "2024-01-01T01:00:00Z",
        }
        item = (
            {
                "hd": header,
                "raw_symbol": "GCZ4",
                "instrument_class": "F",
                "currency": "USD",
            }
            if kwargs["params"]["schema"] == "definition"
            else {"hd": header, "symbol": "GCZ4", "price": "2000", "sequence": 1}
        )
        return json.dumps(item).encode(), None

    monkeypatch.setattr(http_safety, "safe_get_bytes", get)
    with pytest.raises(ValueError, match="expiry"):
        sources.read_commodity(
            "secret",
            dataset="GLBX.MDP3",
            symbol="GCZ4",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            **IDENTITY,
        )


def test_twelve_data_gold_spot_quote_preserves_minute_time(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return {"symbol": "XAU/USD", "last_quote_at": 1704067200, "close": "2020.25"}

    monkeypatch.setenv("TWELVE_DATA_API_KEY", "spot-secret")
    monkeypatch.setattr(sources, "safe_get_json", get)
    record = ExchangeReadOperations(PaperBackend()).get_multi_asset_records(
        "commodity_spot", **IDENTITY, mode="delta"
    )["records"][0]
    assert record["basis"] == "spot"
    assert record["instrument_id"] == "XAU/USD"
    assert record["price"] == 2020.25
    assert record["event_time_utc"] == "2024-01-01T00:00:00+00:00"
    assert calls[0][1]["headers"] == {"Authorization": "apikey spot-secret"}
    assert calls[0][1]["max_redirects"] == 0
    assert "spot-secret" not in calls[0][0]


def test_gold_spot_requires_provider_identity_and_minute_time(monkeypatch):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "spot-secret")
    ops = ExchangeReadOperations(PaperBackend())
    for payload in (
        {"symbol": "XAG/USD", "last_quote_at": 1704067200, "close": "20"},
        {"symbol": "XAU/USD", "close": "2020"},
        {"symbol": "XAU/USD", "last_quote_at": 1704067200, "close": "NaN"},
    ):
        monkeypatch.setattr(
            sources, "safe_get_json", lambda *_a, result=payload, **_kw: result
        )
        with pytest.raises(RuntimeError, match="multi-asset provider read failed"):
            ops.get_multi_asset_records("commodity_spot", **IDENTITY, mode="delta")
