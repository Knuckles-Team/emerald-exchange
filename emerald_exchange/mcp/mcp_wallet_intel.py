"""Wallet Intelligence MCP Domain — CONCEPT:EX-AHE.harness.ee-27.

Action-routed Polymarket wallet-analytics tool, folded in from the former
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
from typing import Any

from emerald_exchange.data.wallet_intel import NoDatasetConfigured, PolyWalletApi

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
        except Exception:
            pass
    return [w.strip() for w in s.split(",") if w.strip()]


def register_wallet_intel_tools(mcp: Any) -> None:
    """Register the Polymarket wallet-intelligence tool group. CONCEPT:EX-AHE.harness.ee-27."""
    if not _enabled():
        logger.info("WALLET_INTELTOOL disabled; skipping wallet-intel tool group")
        return

    @mcp.tool()
    async def emerald_wallet_intel(
        action: str,
        params_json: str = "{}",
    ) -> str:
        """Polymarket wallet-intelligence operations. CONCEPT:EX-AHE.harness.ee-27.

        Actions:
          - rank_wallets: Smart-money copy-trade targets. params: min_trades,
            min_win_rate, top_k.
          - wallet_profile: Per-wallet stats + open positions. params: wallet.
          - smart_money_convergence: How many target wallets hold the same side.
            params: token, wallets (JSON array or comma-separated), market_id.
          - exit_behavior: % exit before resolution + avg % max profit captured.
            params: wallet.

        Args:
            action: The operation to perform.
            params_json: JSON string containing parameters.
        """
        try:
            params = json.loads(params_json) if params_json else {}
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"invalid params_json: {exc}"})

        client = PolyWalletApi()

        try:
            if action == "rank_wallets":
                result = client.rank_wallets(
                    min_trades=int(params.get("min_trades", 20)),
                    min_win_rate=float(params.get("min_win_rate", 0.55)),
                    top_k=int(params.get("top_k", 25)),
                )
            elif action == "wallet_profile":
                result = client.wallet_profile(params["wallet"])
            elif action == "smart_money_convergence":
                result = client.smart_money_convergence(
                    params["token"],
                    _parse_wallets(params.get("wallets", [])),
                    market_id=params.get("market_id") or None,
                )
            elif action == "exit_behavior":
                result = client.exit_behavior(params["wallet"])
            else:
                return json.dumps({"error": f"Unknown action: {action}"})
        except NoDatasetConfigured as exc:
            return json.dumps({"error": str(exc), "ok": False})
        except KeyError as exc:
            return json.dumps({"error": f"missing required param: {exc}"})
        except Exception as exc:  # noqa: BLE001
            logger.error("wallet-intel error (%s): %s", action, exc)
            return json.dumps({"error": str(exc)})

        return json.dumps(result, default=str)
