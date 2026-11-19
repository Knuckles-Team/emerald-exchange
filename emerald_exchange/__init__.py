"""Emerald Exchange — Unified Finance MCP Server.

CONCEPT:AU-AHE.assimilation.autonomous-trading-ecosystem — Emerald Exchange Core

Provides fully abstracted exchange backends for equities, crypto, and
derivatives trading. All functionality is tool-driven via MCP.
"""

from scion_sdk.connector import Connector
from scion_sdk.connector_identity import connector_version

from emerald_exchange.exchange_operations import ExchangeReadOperations

__version__ = connector_version("emerald_exchange")


def _get_client():
    """Per-call read-only exchange operations over a fresh paper backend."""
    from emerald_exchange.backends import TradingMode, create_backend

    backend = create_backend("paper", {}, TradingMode.PAPER)
    backend.connect()
    return ExchangeReadOperations(backend)


def _register_trading(context):
    """Serve the hand-written trading tools on the declared connector too."""
    from emerald_exchange.trading_surface import register_trading_extension

    register_trading_extension(context)


# The one declared connector identity: the fleet name (SDK-CONNECTOR-CONTROL-R071).
# The SDK serves the read-only exchange operations as per-operation tools under
# the fleet name, so the connector sources declaration matches the served tools;
# the trading tools (orders, risk, analyses) register through the same server.
connector = Connector(
    api=ExchangeReadOperations,
    get_client=_get_client,
    extra_registrations=(_register_trading,),
    instructions="Unified Finance MCP — Exchange backends, risk management, and trading tools",
)

__all__ = ["__version__", "connector"]
