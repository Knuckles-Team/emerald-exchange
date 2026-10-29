"""Emerald Exchange — Unified Finance MCP Server.

CONCEPT:AU-AHE.assimilation.autonomous-trading-ecosystem — Emerald Exchange Core

Provides fully abstracted exchange backends for equities, crypto, and
derivatives trading. All functionality is tool-driven via MCP.
"""

from agent_connector_sdk.connector_identity import connector_version

__version__ = connector_version("emerald_exchange")
