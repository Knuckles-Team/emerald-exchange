"""Fundamentals MCP Domain — CONCEPT:EX-AHE.harness.ee-26.

Action-routed SEC EDGAR fundamentals tool, folded in from the former standalone
``edgar-mcp`` package. Surfaces filings / financials / narrative / full-text
search and a one-call ``forensic_screen`` that chains
``standardize_financials`` → engine ``forensic_report`` (Beneish / Altman /
Piotroski / Sloan) so a single ticker goes filings → verdict.

Tool registration is gated by ``FUNDAMENTALSTOOL`` (set to a falsey value to
disable). The SEC identity is read from ``EDGAR_IDENTITY``. ``edgartools`` is an
optional dependency; missing-dep / missing-identity failures are returned as a
clear ``{"error": ...}`` payload rather than crashing the server.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from emerald_exchange.data.edgar import (
    EdgarApi,
    EdgarIdentityMissing,
    EdgarNotInstalled,
)

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """Whether the fundamentals tool group should be registered."""
    return os.getenv("FUNDAMENTALSTOOL", "True").strip().lower() not in (
        "false",
        "0",
        "no",
        "off",
    )


def register_fundamentals_tools(mcp: Any) -> None:
    """Register the SEC EDGAR fundamentals tool group. CONCEPT:EX-AHE.harness.ee-26."""
    if not _enabled():
        logger.info("FUNDAMENTALSTOOL disabled; skipping fundamentals tool group")
        return

    @mcp.tool()
    async def emerald_fundamentals(
        action: str,
        params_json: str = "{}",
    ) -> str:
        """SEC EDGAR fundamentals operations. CONCEPT:EX-AHE.harness.ee-26.

        Actions:
          - filings: Latest N filings of a form. params: ticker, form, latest.
          - financials: Standardized statement. params: ticker, statement
            (income/balance/cashflow).
          - risk_factors: Item 1A, this year + prior year. params: ticker.
          - mdna: Item 7 MD&A, this year + prior year. params: ticker.
          - full_text_search: EDGAR phrase search. params: query, forms, limit.
          - standardize: Two latest fiscal years → 17-key forensic schema.
            params: ticker.
          - forensic_screen: Chain standardize → engine forensic_report
            (Beneish/Altman/Piotroski/Sloan verdict). params: ticker.

        Args:
            action: The operation to perform.
            params_json: JSON string containing parameters.
        """
        try:
            params = json.loads(params_json) if params_json else {}
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"invalid params_json: {type(exc).__name__}"})

        client = EdgarApi()

        try:
            if action == "filings":
                result = client.fetch_filings(
                    params["ticker"],
                    form=params.get("form", "10-K"),
                    latest=int(params.get("latest", 5)),
                )
            elif action == "financials":
                result = client.get_financials(
                    params["ticker"],
                    statement=params.get("statement", "income"),
                )
            elif action == "risk_factors":
                result = client.get_risk_factors(params["ticker"])
            elif action == "mdna":
                result = client.get_mdna(params["ticker"])
            elif action == "full_text_search":
                result = client.full_text_search(
                    params["query"],
                    forms=params.get("forms") or None,
                    limit=int(params.get("limit", 20)),
                )
            elif action == "standardize":
                result = client.standardize_financials(params["ticker"])
            elif action == "forensic_screen":
                result = _forensic_screen(client, params["ticker"])
            else:
                return json.dumps({"error": f"Unknown action: {action}"})
        except (EdgarNotInstalled, EdgarIdentityMissing) as exc:
            return json.dumps({"error": "Operation failed", "ok": False})
        except KeyError as exc:
            return json.dumps({"error": f"missing required param: {type(exc).__name__}"})
        except Exception as exc:  # noqa: BLE001
            logger.error("Operation failed: error_type=%s", type(exc).__name__)
            return json.dumps({"error": "Operation failed"})

        return json.dumps(result, default=str)


def _forensic_screen(client: EdgarApi, ticker: str) -> dict[str, Any]:
    """Chain standardize_financials → engine forensic_report for one ticker.

    Returns the engine verdict plus the standardized input years and the periods
    used, or an ``{"error": ...}`` payload when the engine is unreachable / the
    filing could not be standardized.
    """
    from emerald_exchange.forensic import forensic_screen as engine_forensic_screen

    # standardize_financials already emits the exact 17-key forensic_report
    # schema the engine kernel expects, so the two years pass straight through.
    std = client.standardize_financials(ticker)
    verdict = engine_forensic_screen(
        std.get("this_year", {}), std.get("prior_year", {})
    )
    return {
        "ticker": ticker,
        "periods": std.get("periods", []),
        "this_year": std.get("this_year", {}),
        "prior_year": std.get("prior_year", {}),
        "forensic": verdict,
    }
