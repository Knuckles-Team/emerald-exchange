"""Fundamentals MCP Domain — CONCEPT:EX-AHE.harness.ee-26.

SEC EDGAR fundamentals, one typed tool per operation, folded in from the
former standalone ``edgar-mcp`` package. Surfaces filings / financials /
narrative / full-text search and a one-call forensic screen that chains
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
from collections.abc import Callable
from typing import Annotated, Any, Literal

from pydantic import Field

from emerald_exchange.data.edgar import (
    EdgarApi,
    EdgarIdentityMissing,
    EdgarNotInstalled,
)
from emerald_exchange.mcp._hints import READ

logger = logging.getLogger(__name__)

Ticker = Annotated[str, Field(description="Company ticker, for example AAPL")]


def _enabled() -> bool:
    """Whether the fundamentals tool group should be registered."""
    return os.getenv("FUNDAMENTALSTOOL", "True").strip().lower() not in (
        "false",
        "0",
        "no",
        "off",
    )


def _run(operation: Callable[[EdgarApi], Any]) -> str:
    """Run one EDGAR operation; optional-dep failures become an error payload."""
    try:
        result = operation(EdgarApi())
    except (EdgarNotInstalled, EdgarIdentityMissing):
        return json.dumps({"error": "Operation failed", "ok": False})
    except Exception as exc:  # noqa: BLE001
        logger.error("Operation failed: error_type=%s", type(exc).__name__)
        return json.dumps({"error": "Operation failed"})
    return json.dumps(result, default=str)


def register_fundamentals_tools(mcp: Any) -> None:
    """Register the SEC EDGAR fundamentals tool group. CONCEPT:EX-AHE.harness.ee-26."""
    if not _enabled():
        logger.info("FUNDAMENTALSTOOL disabled; skipping fundamentals tool group")
        return

    @mcp.tool(tags={"fundamentals"}, annotations=READ)
    async def emerald_fundamentals_filings(
        ticker: Ticker,
        form: Annotated[
            str, Field(description="Filing form, for example 10-K")
        ] = "10-K",
        latest: Annotated[int, Field(description="How many filings")] = 5,
    ) -> str:
        """Latest N filings of a form. CONCEPT:EX-AHE.harness.ee-26"""
        return _run(lambda c: c.fetch_filings(ticker, form=form, latest=latest))

    @mcp.tool(tags={"fundamentals"}, annotations=READ)
    async def emerald_fundamentals_financials(
        ticker: Ticker,
        statement: Literal["income", "balance", "cashflow"] = "income",
    ) -> str:
        """Standardized financial statement. CONCEPT:EX-AHE.harness.ee-26"""
        return _run(lambda c: c.get_financials(ticker, statement=statement))

    @mcp.tool(tags={"fundamentals"}, annotations=READ)
    async def emerald_fundamentals_risk_factors(ticker: Ticker) -> str:
        """Item 1A risk factors, this year and prior year. CONCEPT:EX-AHE.harness.ee-26"""
        return _run(lambda c: c.get_risk_factors(ticker))

    @mcp.tool(tags={"fundamentals"}, annotations=READ)
    async def emerald_fundamentals_mdna(ticker: Ticker) -> str:
        """Item 7 MD&A, this year and prior year. CONCEPT:EX-AHE.harness.ee-26"""
        return _run(lambda c: c.get_mdna(ticker))

    @mcp.tool(tags={"fundamentals"}, annotations=READ)
    async def emerald_fundamentals_full_text_search(
        query: Annotated[str, Field(description="Phrase to search filings for")],
        forms: Annotated[
            list[str] | None, Field(description="Restrict to these forms")
        ] = None,
        limit: Annotated[int, Field(description="Maximum hits")] = 20,
    ) -> str:
        """EDGAR full-text phrase search. CONCEPT:EX-AHE.harness.ee-26"""
        return _run(
            lambda c: c.full_text_search(query, forms=forms or None, limit=limit)
        )

    @mcp.tool(tags={"fundamentals"}, annotations=READ)
    async def emerald_fundamentals_standardize(ticker: Ticker) -> str:
        """Two latest fiscal years in the 17-key forensic schema. CONCEPT:EX-AHE.harness.ee-26"""
        return _run(lambda c: c.standardize_financials(ticker))

    @mcp.tool(tags={"fundamentals"}, annotations=READ)
    async def emerald_fundamentals_forensic_screen(ticker: Ticker) -> str:
        """Standardize then engine forensic_report: Beneish/Altman/Piotroski/Sloan verdict.

        CONCEPT:EX-AHE.harness.ee-26
        """
        return _run(lambda c: _forensic_screen(c, ticker))


def _forensic_screen(client: EdgarApi, ticker: str) -> dict[str, Any]:
    """Chain standardize_financials → engine forensic_report for one ticker.

    Returns the engine verdict plus the standardized input years and the periods
    used, or an ``{"error": ...}`` payload when the engine is unreachable / the
    filing could not be standardized.
    """
    from emerald_exchange.analyses import forensic_screen as engine_forensic_screen

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
