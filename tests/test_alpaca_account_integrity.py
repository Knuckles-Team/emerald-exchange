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
