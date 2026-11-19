"""The hand-written trading tools, one typed tool per operation.

Orders, risk, signals, strategy, analyses and ingestion are not exchange API
reads, so the SDK does not derive them from :class:`ExchangeReadOperations`.
:func:`register_trading_tools` registers them on a server; the declared
connector runs it through :func:`register_trading_extension`, and the console
script runs it directly, so both serve the same surface.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from scion_sdk.config import setting

from emerald_exchange.backends import ExchangeBackend
from emerald_exchange.risk_guards import RiskGuard

logger = logging.getLogger(__name__)


@dataclass
class TradingState:
    """The exchange backend and risk guard every trading tool shares."""

    backend: ExchangeBackend
    risk_guard: RiskGuard
    config: dict[str, Any] = field(default_factory=dict)


def load_config_file() -> dict[str, Any]:
    """The connector's ``config.json``; empty when absent or unreadable."""
    from scion_sdk import paths

    config_path = paths.config_dir() / "config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path) as f:
            loaded = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Operation failed: error_type=%s", type(e).__name__)
        return {}
    return loaded if isinstance(loaded, dict) else {}


def build_trading_state(full_config: dict[str, Any] | None = None) -> TradingState:
    """Connect the configured exchange backend and build its risk guard."""
    from emerald_exchange.backends import TradingMode, create_backend
    from emerald_exchange.risk_guards import RiskLimits

    config = load_config_file() if full_config is None else full_config
    trading_config = config.get("trading", {})
    default_exchange = trading_config.get("default_exchange", "paper")
    default_mode = TradingMode(trading_config.get("default_mode", "paper"))
    exchange_config = trading_config.get("exchanges", {}).get(default_exchange, {})

    # Resolve env vars for API keys
    resolved_config: dict = {}
    for key, val in exchange_config.items():
        if isinstance(val, str) and key.endswith("_env"):
            resolved_config[key.replace("_env", "")] = setting(val, "")
        elif key not in ("enabled",):
            resolved_config[key] = val

    backend = create_backend(default_exchange, resolved_config, default_mode)
    backend.connect()

    risk_config = trading_config.get("risk_limits", {})
    risk_guard = RiskGuard(RiskLimits(**risk_config) if risk_config else None)
    return TradingState(backend=backend, risk_guard=risk_guard, config=config)


def register_trading_tools(mcp: Any, state: TradingState) -> list[str]:
    """Register every enabled trading domain; return the enabled tags.

    Each ``<TAG>TOOL`` setting defaults True; an operator can disable a domain.
    """
    from emerald_exchange.mcp.mcp_crypto import register_crypto_tools
    from emerald_exchange.mcp.mcp_debate import register_debate_tools
    from emerald_exchange.mcp.mcp_derivatives import register_derivatives_tools
    from emerald_exchange.mcp.mcp_fundamentals import register_fundamentals_tools
    from emerald_exchange.mcp.mcp_kg_ingest import register_kg_ingest_tools
    from emerald_exchange.mcp.mcp_market_making import register_market_making_tools
    from emerald_exchange.mcp.mcp_orders import register_order_tools
    from emerald_exchange.mcp.mcp_prediction_markets import (
        register_prediction_market_tools,
    )
    from emerald_exchange.mcp.mcp_risk import register_risk_tools
    from emerald_exchange.mcp.mcp_signals import register_signal_tools
    from emerald_exchange.mcp.mcp_statarb import register_statarb_tools
    from emerald_exchange.mcp.mcp_strategy import register_strategy_tools
    from emerald_exchange.mcp.mcp_wallet_intel import register_wallet_intel_tools

    backend, risk_guard = state.backend, state.risk_guard
    registrars = [
        ("crypto", "CRYPTOTOOL", lambda m: register_crypto_tools(m, backend)),
        ("debate", "DEBATETOOL", register_debate_tools),
        ("derivatives", "DERIVATIVESTOOL", register_derivatives_tools),
        ("market_making", "MARKET_MAKINGTOOL", register_market_making_tools),
        ("order", "ORDERTOOL", lambda m: register_order_tools(m, backend, risk_guard)),
        ("risk", "RISKTOOL", lambda m: register_risk_tools(m, backend, risk_guard)),
        ("signal", "SIGNALTOOL", register_signal_tools),
        ("statarb", "STATARBTOOL", register_statarb_tools),
        ("strategy", "STRATEGYTOOL", register_strategy_tools),
        (
            "prediction_market",
            "PREDICTION_MARKETTOOL",
            lambda m: register_prediction_market_tools(m, risk_guard),
        ),
        ("fundamentals", "FUNDAMENTALSTOOL", register_fundamentals_tools),
        ("wallet_intel", "WALLET_INTELTOOL", register_wallet_intel_tools),
        ("kg_ingest", "KG_INGESTTOOL", lambda m: register_kg_ingest_tools(m, backend)),
    ]
    enabled: list[str] = []
    for tag, toggle, registrar in registrars:
        if setting(toggle, True):
            registrar(mcp)
            enabled.append(tag)
        else:
            logger.info("%s disabled; skipping the %s tools", toggle, tag)
    return enabled


def register_trading_extension(context: Any) -> None:
    """Connector registration hook: serve the trading tools on the SDK server."""
    register_trading_tools(context.server, build_trading_state())
