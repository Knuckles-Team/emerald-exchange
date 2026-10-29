"""FMP company feeds use fixed HTTPS sources and preserve provider facts."""

import httpx
import pytest

from emerald_exchange import fmp_company_sources as fmp
from emerald_exchange.backends import AlpacaBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations

PROFILE = {
    "symbol": "AAPL",
    "companyName": "Apple Inc.",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "exchange": "NASDAQ",
    "currency": "USD",
    "image": "https://images.financialmodelingprep.com/symbol/AAPL.png",
    "defaultImage": False,
}
INCOME = {
    "symbol": "AAPL",
    "date": "2025-09-27",
    "period": "FY",
    "reportedCurrency": "USD",
    "revenue": 416161000000,
    "netIncome": 112010000000,
    "filingDate": "2025-10-31",
}
EARNINGS = {
    "symbol": "AAPL",
    "date": "2026-07-30",
    "epsActual": None,
    "epsEstimated": 1.88,
    "revenueActual": None,
    "revenueEstimated": 109038900000,
    "lastUpdated": "2026-07-30",
}
PNG = b"\x89PNG\r\n\x1a\n" + b"test data"


def stub_fmp(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return {
            "profile": [PROFILE],
            "income-statement": [INCOME],
            "earnings": [EARNINGS],
        }[url.rsplit("/", 1)[1]]

    monkeypatch.setattr(fmp, "safe_get_json", get)
    monkeypatch.setattr(fmp, "safe_get_bytes", lambda url, **kw: (PNG, None))
    return calls


def test_profile_income_earnings_logo_through_operations(monkeypatch):
    calls = stub_fmp(monkeypatch)
    ops = ExchangeReadOperations(AlpacaBackend(fmp_api_key="secret"))
    results = {
        kind: ops.get_company_records("AAPL", kind, "operator-license", "delta")[
            "records"
        ][0]
        for kind in ("profile", "income", "earnings", "logo")
    }
    assert results["profile"]["company_name"] == "Apple Inc."
    assert results["income"]["net_income"] == 112010000000
    assert results["earnings"]["eps_estimated"] == 1.88
    assert "eps_actual" not in results["earnings"]
    assert results["logo"]["image_media_type"] == "image/png"
    assert len({item["record_id"] for item in results.values()}) == 4
    assert all(
        c[1]["headers"] == {"apikey": "secret"} and c[1]["max_redirects"] == 0
        for c in calls
    )
    assert all("secret" not in c[0] for c in calls)


def test_bad_values_and_duplicate_events_are_redacted(monkeypatch):
    stub_fmp(monkeypatch)
    monkeypatch.setattr(
        fmp, "safe_get_json", lambda *_a, **_kw: [{**INCOME, "netIncome": float("nan")}]
    )
    ops = ExchangeReadOperations(AlpacaBackend(fmp_api_key="secret"))
    with pytest.raises(RuntimeError, match="company data read failed") as error:
        ops.get_company_records("AAPL", "income", "licensed", "delta")
    assert "secret" not in str(error.value)
    monkeypatch.setattr(fmp, "safe_get_json", lambda *_a, **_kw: [EARNINGS, EARNINGS])
    with pytest.raises(RuntimeError, match="company data read failed"):
        ops.get_company_records("AAPL", "earnings", "licensed", "delta")


def test_http_error_and_untrusted_logo_are_redacted(monkeypatch):
    stub_fmp(monkeypatch)
    ops = ExchangeReadOperations(AlpacaBackend(fmp_api_key="secret"))

    def fail(*_a, **_kw):
        raise httpx.ConnectError("private provider detail")

    monkeypatch.setattr(fmp, "safe_get_json", fail)
    with pytest.raises(RuntimeError) as error:
        ops.get_company_records("AAPL", "profile", "licensed", "delta")
    assert "private provider detail" not in str(error.value)
    monkeypatch.setattr(
        fmp,
        "safe_get_json",
        lambda *_a, **_kw: [{**PROFILE, "image": "https://evil.invalid/secret.png"}],
    )
    with pytest.raises(RuntimeError):
        ops.get_company_records("AAPL", "logo", "licensed", "delta")


def test_actual_guarded_http_transport_sends_key_in_header(monkeypatch):
    from agent_connector_sdk.source_connectors.http_safety import safe_get_json

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[PROFILE])

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        fmp,
        "safe_get_json",
        lambda url, **kw: safe_get_json(url, transport=transport, **kw),
    )
    records = ExchangeReadOperations(
        AlpacaBackend(fmp_api_key="test-secret")
    ).get_company_records("AAPL", "profile", "licensed", "delta")["records"]
    assert records[0]["company_name"] == "Apple Inc."
    assert requests[0].headers["apikey"] == "test-secret"
    assert "test-secret" not in str(requests[0].url)
