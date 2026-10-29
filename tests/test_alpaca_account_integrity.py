"""The configured account must come from Alpaca, never a fabricated fallback."""

import asyncio
from types import SimpleNamespace

import pytest

from emerald_exchange.backends import AlpacaBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations

pytestmark = pytest.mark.spec("EMERALD-OPS-R003")


class Provider:
    def get_account(self):
        return SimpleNamespace(
            id="account-1", currency="USD", equity="10", cash="9", buying_power="8"
        )

    def get_all_positions(self):
        return [
            SimpleNamespace(
                symbol="ABC",
                qty="1",
                avg_entry_price="2",
                current_price="3",
                unrealized_pl="1",
            )
        ]


def _operations(provider):
    backend = AlpacaBackend()
    backend._client = provider
    return ExchangeReadOperations(backend)


def test_account_identity_and_positions_are_from_provider():
    operations = _operations(Provider())
    account = operations.get_account()
    assert account.account_id == "account-1"
    assert account.currency == "USD"
    assert operations.get_positions()[0].symbol == "ABC"


@pytest.mark.parametrize("operation", ["get_account", "get_all_positions"])
def test_provider_read_failure_is_not_fabricated(operation):
    provider = Provider()

    def fail():
        raise ConnectionError("provider unavailable")

    setattr(provider, operation, fail)
    operations = _operations(provider)
    read = (
        operations.get_account
        if operation == "get_account"
        else operations.get_positions
    )
    with pytest.raises(RuntimeError, match="read failed"):
        read()


def test_invalid_account_identity_and_nonfinite_balance_refuse():
    provider = Provider()
    provider.get_account = lambda: SimpleNamespace(
        id=None, currency="USD", equity="10", cash="9", buying_power="8"
    )
    with pytest.raises(RuntimeError, match="read failed"):
        _operations(provider).get_account()
    provider.get_account = lambda: SimpleNamespace(
        id="account-1", currency="USD", equity="nan", cash="9", buying_power="8"
    )
    with pytest.raises(RuntimeError, match="read failed"):
        _operations(provider).get_account()


def test_real_served_account_tool_exposes_provider_identity():
    from agent_connector_sdk.mcp.server import create_mcp_server
    from agent_connector_sdk.mcp.tool_surface import register_tool_surface
    from fastmcp import Client

    server = create_mcp_server("synthetic-exchange", version="0", command_args=[])[1]
    operations = _operations(Provider())
    register_tool_surface(
        server,
        service="synthetic-exchange",
        registrars=[],
        verbose_targets=[
            {
                "client_cls": ExchangeReadOperations,
                "get_client": lambda: operations,
                "tool_prefix": "emerald",
            }
        ],
    )

    async def run():
        async with Client(server) as client:
            result = await client.call_tool("synthetic_exchange_get_account", {})
            return result.data

    assert asyncio.run(run())["account_id"] == "account-1"


def test_real_served_provider_failure_does_not_expose_details():
    from agent_connector_sdk.mcp.server import create_mcp_server
    from agent_connector_sdk.mcp.tool_surface import register_tool_surface
    from fastmcp import Client

    provider = Provider()

    def fail():
        raise ConnectionError("provider-private-detail")

    provider.get_account = fail
    operations = _operations(provider)
    server = create_mcp_server("synthetic-exchange", version="0", command_args=[])[1]
    register_tool_surface(
        server,
        service="synthetic-exchange",
        registrars=[],
        verbose_targets=[
            {
                "client_cls": ExchangeReadOperations,
                "get_client": lambda: operations,
                "tool_prefix": "emerald",
            }
        ],
    )

    async def run():
        async with Client(server) as client:
            return await client.call_tool(
                "synthetic_exchange_get_account", {}, raise_on_error=False
            )

    result = asyncio.run(run())
    assert result.is_error
    assert "provider-private-detail" not in str(result)


def test_documented_provider_exception_is_redacted():
    class ProviderApiError(Exception):
        pass

    provider = Provider()

    def fail():
        raise ProviderApiError("provider-private-detail")

    provider.get_account = fail
    backend = AlpacaBackend()
    backend._client = provider
    backend._read_errors = (*backend._read_errors, ProviderApiError)
    with pytest.raises(RuntimeError) as error:
        backend.get_account()
    assert "provider-private-detail" not in str(error.value)


@pytest.mark.spec("EMERALD-OPS-R004")
def test_snapshot_source_is_declared_and_served():
    from agent_connector_sdk.mcp.server import create_mcp_server
    from agent_connector_sdk.mcp.tool_surface import register_tool_surface
    from fastmcp import Client

    from emerald_exchange.connector_sources import SOURCES

    declaration = next(
        item
        for group in SOURCES
        for item in group["connector_sources"]
        if item["source_id"] == "alpaca-account"
    )
    assert declaration["tool"] == "emerald_exchange_get_account_snapshot"
    assert declaration["id_field"] == "account_id"
    operations = _operations(Provider())
    server = create_mcp_server("emerald-exchange-mcp", version="0", command_args=[])[1]
    register_tool_surface(
        server,
        service="emerald-exchange",
        registrars=[],
        verbose_targets=[
            {
                "client_cls": ExchangeReadOperations,
                "get_client": lambda: operations,
                "tool_prefix": "emerald",
            }
        ],
    )

    async def run():
        async with Client(server) as client:
            return (await client.call_tool(declaration["tool"], {})).data

    result = asyncio.run(run())
    assert len(result) == 1
    assert result[0]["account_id"] == "account-1"
    assert result[0]["positions"][0]["symbol"] == "ABC"


@pytest.mark.spec("EMERALD-OPS-R004")
def test_snapshot_source_refuses_incomplete_account_or_position_reads():
    from emerald_exchange.backends import PaperBackend

    with pytest.raises(ValueError, match="Alpaca"):
        ExchangeReadOperations(PaperBackend()).get_account_snapshot()
    provider = Provider()

    def fail():
        raise ConnectionError("provider unavailable")

    provider.get_all_positions = fail
    with pytest.raises(RuntimeError, match="read failed"):
        _operations(provider).get_account_snapshot()


@pytest.mark.spec("EMERALD-OPS-R004")
def test_sdk_mcp_adapter_extracts_the_declared_account_snapshot():
    from agent_connector_sdk.adapters.mcp_tool import McpToolSourceAdapter
    from agent_connector_sdk.manifest.presets import ToolPreset
    from agent_connector_sdk.mcp.server import create_mcp_server
    from agent_connector_sdk.mcp.tool_surface import register_tool_surface
    from agent_connector_sdk.ports.session import TransportEndpoint
    from agent_connector_sdk.transports.mcp import McpTransport

    from agent_connector_sdk.ingest.live_declaration import load_declaration as declaration

    source = next(s for s in declaration("emerald_exchange").sources if s.source_id == "alpaca-account")
    preset = ToolPreset(
        name=source.source_id,
        server="emerald-exchange-mcp",
        tool=source.tools[0],
        params_style="args",
        id_field=source.id_field,
        text_field=source.text_field,
        title_field=source.title_field,
        doc_type="account",
    )
    adapter = McpToolSourceAdapter(
        preset,
        connector="emerald-exchange-mcp",
        mapping_reference="connector:emerald-exchange-mcp#mappings/Account",
    )
    server = create_mcp_server("emerald-exchange-mcp", version="0", command_args=[])[1]
    operations = _operations(Provider())
    register_tool_surface(
        server,
        service="emerald-exchange",
        registrars=[],
        verbose_targets=[
            {
                "client_cls": ExchangeReadOperations,
                "get_client": lambda: operations,
                "tool_prefix": "emerald",
            }
        ],
    )

    async def run():
        async with McpTransport().session(
            TransportEndpoint(in_process=server)
        ) as session:
            await adapter.discover(session)
            return await adapter.extract(session, None)

    page = asyncio.run(run())
    assert len(page.records) == 1
    assert page.records[0].record_id == "account-1"
    assert page.records[0].payload["positions"][0]["symbol"] == "ABC"


def test_account_positions_source_binds_stable_account_and_symbol_identity():
    from emerald_exchange.connector_sources import SOURCES, SCHEMA_MAPPINGS

    source = next(
        item
        for group in SOURCES
        for item in group["connector_sources"]
        if item["source_id"] == "alpaca-account-positions"
    )
    assert source["tool"] == "emerald_exchange_get_account_positions"
    assert source["id_field"] == "position_id"
    first = _operations(Provider()).get_account_positions()
    repeat = _operations(Provider()).get_account_positions()
    assert first == repeat
    assert first[0]["account_id"] == "account-1"
    assert first[0]["symbol"] == "ABC"
    assert first[0]["qty"] == 1
    assert all(key in SCHEMA_MAPPINGS["Position"]["fields"] for key in (
        "account_id", "symbol", "qty", "avg_entry_price", "current_price", "unrealized_pnl"
    ))

    provider = Provider()
    provider.get_account = lambda: SimpleNamespace(
        id="account-2", currency="USD", equity="10", cash="9", buying_power="8"
    )
    assert _operations(provider).get_account_positions()[0]["position_id"] != first[0]["position_id"]


def test_account_positions_source_refuses_incomplete_reads():
    provider = Provider()

    def fail():
        raise ConnectionError("provider unavailable")

    provider.get_all_positions = fail
    with pytest.raises(RuntimeError, match="read failed"):
        _operations(provider).get_account_positions()


@pytest.mark.parametrize("symbols", [["", "ABC"], ["ABC", "ABC"]])
def test_account_positions_refuses_missing_or_duplicate_symbols(symbols):
    provider = Provider()
    provider.get_all_positions = lambda: [
        SimpleNamespace(symbol=symbol, qty="1", avg_entry_price="2", current_price="3", unrealized_pl="1")
        for symbol in symbols
    ]
    with pytest.raises(ValueError, match="symbol"):
        _operations(provider).get_account_positions()
