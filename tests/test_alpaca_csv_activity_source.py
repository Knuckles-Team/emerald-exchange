"""CSV activity source is account-bound and refuses invalid input."""

from types import SimpleNamespace

import pytest
from scion_sdk.ingest.live_declaration import load_declaration as declaration

from emerald_exchange.backends import AlpacaBackend, PaperBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations

CSV = "date,side,qty,price,fee,ccy,settle\n2026-01-02T00:00:00Z,buy,10,100.5,1,USD,2026-01-04T00:00:00Z\n"
MAPPING = {
    "date": "event_time_utc",
    "side": "action",
    "qty": "quantity",
    "price": "price",
    "fee": "fees",
    "ccy": "currency",
    "settle": "settlement_time_utc",
}


def operations(account_id):
    backend = AlpacaBackend()
    backend._client = SimpleNamespace(
        get_account=lambda: SimpleNamespace(
            id=account_id, currency="USD", equity="10", cash="9", buying_power="8"
        )
    )
    return ExchangeReadOperations(backend)


def read(ops, content=CSV):
    return ops.get_csv_activities(
        content, MAPPING, "tenant-1", "ABC", "licensed", "delta"
    )


def test_declared_source_binds_activity_to_provider_account():
    source = next(
        item
        for item in declaration("emerald_exchange").sources
        if item.source_id == "alpaca-csv-activities"
    )
    assert source.tools == ("emerald_exchange_get_csv_activities",)
    assert source.id_field == "record_id"
    first = read(operations("account-1"))
    repeat = read(operations("account-1"))
    different = read(operations("account-2"))
    assert first["records"][0]["account_id"] == "account-1"
    assert first["records"][0]["record_id"] == repeat["records"][0]["record_id"]
    assert first["records"][0]["record_id"] != different["records"][0]["record_id"]
    assert first["checkpoint"] != repeat["checkpoint"]


def test_invalid_statement_and_non_alpaca_backend_refuse():
    with pytest.raises(ValueError, match="Invalid CSV") as error:
        read(operations("account-1"), CSV.replace("USD", "private-value"))
    assert "private-value" not in str(error.value)
    with pytest.raises(ValueError, match="Alpaca"):
        read(ExchangeReadOperations(PaperBackend()))


def test_actual_server_serves_the_account_activity_declaration(monkeypatch):
    import asyncio
    import json
    import sys

    from fastmcp import Client

    import emerald_exchange.backends as backends
    from emerald_exchange.mcp_server import get_mcp_instance

    monkeypatch.setattr(backends, "create_backend", lambda *_: PaperBackend())
    monkeypatch.setattr(sys, "argv", ["emerald-exchange", "--transport", "stdio"])
    server = get_mcp_instance()[0]

    async def read_resource():
        async with Client(server) as client:
            resources = {str(item.uri) for item in await client.list_resources()}
            assert "connector://resources" in resources
            contents = await client.read_resource("connector://resources")
            return json.loads(contents[0].text)

    body = asyncio.run(read_resource())
    assert {item["source_id"] for item in body["sources"]} >= {
        "alpaca-account",
        "alpaca-account-positions",
        "alpaca-csv-activities",
    }
    assert "Activity" in body["schema_mappings"]
