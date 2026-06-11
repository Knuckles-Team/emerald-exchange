"""Emerald Exchange MCP Server

Unified Finance MCP exposing all trading tools via action-routed domains.
"""

import json
import logging
import os
import sys

logger = logging.getLogger(__name__)


def get_mcp_instance():
    """Build the Emerald Exchange MCP server (FastMCP instance + parsed args)."""
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from agent_utilities.mcp_utilities import create_mcp_server

    args, mcp, middlewares = create_mcp_server(
        name="emerald-exchange",
        instructions="Unified Finance MCP — Exchange backends, risk management, and trading tools",
    )

    from emerald_exchange.mcp.mcp_crypto import register_crypto_tools
    from emerald_exchange.mcp.mcp_debate import register_debate_tools
    from emerald_exchange.mcp.mcp_derivatives import register_derivatives_tools
    from emerald_exchange.mcp.mcp_fundamentals import register_fundamentals_tools
    from emerald_exchange.mcp.mcp_market_data import register_market_data_tools
    from emerald_exchange.mcp.mcp_market_making import register_market_making_tools
    from emerald_exchange.mcp.mcp_orders import register_order_tools
    from emerald_exchange.mcp.mcp_portfolio import register_portfolio_tools
    from emerald_exchange.mcp.mcp_risk import register_risk_tools
    from emerald_exchange.mcp.mcp_signals import register_signal_tools
    from emerald_exchange.mcp.mcp_statarb import register_statarb_tools
    from emerald_exchange.mcp.mcp_strategy import register_strategy_tools
    from emerald_exchange.mcp.mcp_prediction_markets import (
        register_prediction_market_tools,
    )
    from emerald_exchange.mcp.mcp_wallet_intel import register_wallet_intel_tools

    # Load config
    from agent_utilities.core import paths

    config_path = paths.config_dir() / "config.json"
    trading_config: dict = {}
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                full_config = json.load(f)
            trading_config = full_config.get("trading", {})
        except Exception as e:
            logger.warning("Failed to load trading config: %s", e)

    # Initialize exchange backend
    from emerald_exchange.backends import TradingMode, create_backend
    from emerald_exchange.risk_guards import RiskGuard, RiskLimits

    default_exchange = trading_config.get("default_exchange", "paper")
    default_mode = TradingMode(trading_config.get("default_mode", "paper"))
    exchange_config = trading_config.get("exchanges", {}).get(default_exchange, {})

    # Resolve env vars for API keys
    resolved_config: dict = {}
    for key, val in exchange_config.items():
        if isinstance(val, str) and key.endswith("_env"):
            resolved_config[key.replace("_env", "")] = os.environ.get(val, "")
        elif key not in ("enabled",):
            resolved_config[key] = val

    backend = create_backend(default_exchange, resolved_config, default_mode)
    backend.connect()

    # Initialize risk guard
    risk_config = trading_config.get("risk_limits", {})
    risk_guard = RiskGuard(RiskLimits(**risk_config) if risk_config else None)

    print(
        f"🟢 Emerald Exchange MCP: {default_exchange} ({default_mode})", file=sys.stderr
    )

    # Register all 8 tool domains
    register_crypto_tools(mcp, backend)
    register_debate_tools(mcp)
    register_derivatives_tools(mcp)
    register_market_data_tools(mcp, backend)
    register_market_making_tools(mcp)
    register_order_tools(mcp, backend, risk_guard)
    register_portfolio_tools(mcp, backend)
    register_risk_tools(mcp, backend, risk_guard)
    register_signal_tools(mcp)
    register_statarb_tools(mcp)
    register_strategy_tools(mcp)
    register_prediction_market_tools(mcp, risk_guard)
    register_fundamentals_tools(mcp)
    register_wallet_intel_tools(mcp)

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
