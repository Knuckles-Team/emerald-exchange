"""Wallet Intelligence MCP Domain — CONCEPT:EX-AHE.harness.ee-27.

Polymarket wallet analytics, one typed tool per operation, folded in from the former
standalone ``poly-wallet-mcp`` package. Over a ``poly_data`` trade dataset it
finds smart-money wallets, profiles them, measures convergence on a token, and
studies exit behavior.

Tool registration is gated by ``WALLET_INTELTOOL`` (set to a falsey value to
disable). The dataset path is read from ``POLY_TRADES_PATH``. ``polars`` is an
optional fast/Parquet loader; an unconfigured / missing dataset is returned as a
clear ``{"error": ...}`` payload rather than crashing the server.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import Field

from emerald_exchange.data.wallet_intel import NoDatasetConfigured, PolyWalletApi
from emerald_exchange.mcp._hints import READ

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """Whether the wallet-intel tool group should be registered."""
    return os.getenv("WALLET_INTELTOOL", "True").strip().lower() not in (
        "false",
        "0",
        "no",
        "off",
    )


def _parse_wallets(wallets: Any) -> list[str]:
    """Accept a JSON array, comma-separated string, or list of addresses."""
    if isinstance(wallets, list):
        return [str(w) for w in wallets]
    s = str(wallets or "").strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            return [str(w) for w in json.loads(s)]
        except (ValueError, TypeError):
            return [w.strip() for w in s.split(",") if w.strip()]
    return [w.strip() for w in s.split(",") if w.strip()]


def _run(operation: Callable[[PolyWalletApi], Any]) -> str:
    """Run one wallet analysis; a missing dataset becomes an error payload."""
    try:
        result = operation(PolyWalletApi())
    except NoDatasetConfigured:
        return json.dumps({"error": "Operation failed", "ok": False})
    except Exception as exc:  # noqa: BLE001
        logger.error("Operation failed: error_type=%s", type(exc).__name__)
        return json.dumps({"error": "Operation failed"})
    return json.dumps(result, default=str)


Wallet = Annotated[str, Field(description="Wallet address")]


def register_wallet_intel_tools(mcp: Any) -> None:
    """Register the Polymarket wallet-intelligence tool group. CONCEPT:EX-AHE.harness.ee-27."""
    if not _enabled():
        logger.info("WALLET_INTELTOOL disabled; skipping wallet-intel tool group")
        return

    @mcp.tool(tags={"wallet_intel"}, annotations=READ)
    async def emerald_wallet_intel_rank_wallets(
        min_trades: Annotated[int, Field(description="Minimum trades")] = 20,
        min_win_rate: Annotated[float, Field(description="Minimum win rate")] = 0.55,
        top_k: Annotated[int, Field(description="How many wallets")] = 25,
    ) -> str:
        """Smart-money copy-trade targets. CONCEPT:EX-AHE.harness.ee-27"""
        return _run(
            lambda c: c.rank_wallets(
                min_trades=min_trades, min_win_rate=min_win_rate, top_k=top_k
            )
        )

    @mcp.tool(tags={"wallet_intel"}, annotations=READ)
    async def emerald_wallet_intel_wallet_profile(wallet: Wallet) -> str:
        """Per-wallet stats and open positions. CONCEPT:EX-AHE.harness.ee-27"""
        return _run(lambda c: c.wallet_profile(wallet))

    @mcp.tool(tags={"wallet_intel"}, annotations=READ)
    async def emerald_wallet_intel_smart_money_convergence(
        token: Annotated[str, Field(description="Outcome token id")],
        wallets: Annotated[
            list[str] | str,
            Field(description="Target wallets: a list, JSON array or comma-separated"),
        ],
        market_id: Annotated[str, Field(description="Optional market id")] = "",
    ) -> str:
        """How many target wallets hold the same side of a token. CONCEPT:EX-AHE.harness.ee-27"""
        return _run(
            lambda c: c.smart_money_convergence(
                token, _parse_wallets(wallets), market_id=market_id or None
            )
        )

    @mcp.tool(tags={"wallet_intel"}, annotations=READ)
    async def emerald_wallet_intel_exit_behavior(wallet: Wallet) -> str:
        """Share exited before resolution and average share of max profit captured.

        CONCEPT:EX-AHE.harness.ee-27
        """
        return _run(lambda c: c.exit_behavior(wallet))
