"""Emerald Exchange MCP Server

Unified Finance MCP: one typed tool per trading, analysis and exchange operation.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def get_mcp_instance():
    """Build the Emerald Exchange MCP server (FastMCP instance + parsed args)."""
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from scion_sdk.config import load_config
    from scion_sdk.mcp.content import ConnectorContent
    from scion_sdk.mcp.server import create_mcp_server
    from scion_sdk.mcp.tool_surface import register_tool_surface

    load_config()

    from emerald_exchange import __version__

    args, mcp, middlewares = create_mcp_server(
        name="emerald-exchange",
        version=__version__,
        instructions="Unified Finance MCP — Exchange backends, risk management, and trading tools",
        content=ConnectorContent.for_package(
            "emerald_exchange",
            Path(__file__).resolve().parent,
            __version__,
        ),
    )

    from emerald_exchange.trading_surface import (
        build_trading_state,
        register_trading_tools,
    )

    state = build_trading_state()
    backend = state.backend
    print(f"🟢 Emerald Exchange MCP: {backend.name} ({backend.mode})", file=sys.stderr)

    # Exchange API operations: one typed tool per backend method. Quotes,
    # history, positions and account reads are these operation tools.
    from emerald_exchange.exchange_operations import ExchangeReadOperations

    read_operations = ExchangeReadOperations(backend)
    registered_tags = register_tool_surface(
        mcp,
        service="emerald-exchange",
        package_root=Path(__file__).parent,
        registrars=[],
        verbose_targets=[
            {
                # Reads only: order writes stay behind the risk guard.
                "client_cls": ExchangeReadOperations,
                "get_client": lambda: read_operations,
                "tool_prefix": "emerald",
            }
        ],
    )
    logger.debug("Registered tool domains: %s", registered_tags)

    # Orders, risk, signals, strategy and analyses: one typed tool each.
    register_trading_tools(mcp, state)

    for mw in middlewares:
        mcp.add_middleware(mw)

    return mcp, args, middlewares


def mcp_server() -> None:
    """Console-script entry point: build the server and run the selected transport."""
    mcp, args, _middlewares = get_mcp_instance()
    print("Emerald Exchange MCP", file=sys.stderr)
    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    mcp_server()
