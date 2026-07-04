"""Forensic Accounting Screener — CONCEPT:EX-AHE.harness.ee-25.

Thin controller over the Rust ``epistemic-graph`` engine's ``forensic_report``
(Beneish M-Score / Altman Z-Score / Piotroski F-Score / Sloan accruals over two
fiscal years). emerald-exchange owns no forensic math — it standardizes the two
input years and surfaces the verdict.
"""

from __future__ import annotations

import logging
from typing import Any

from emerald_exchange._engine import ENGINE_REQUIRED_ERR, finance_engine

logger = logging.getLogger(__name__)

# Standardized line items the engine expects per fiscal year — the exact 17-key
# forensic_report (YearData) schema emitted by ``data/edgar.standardize_financials``
# and consumed by the live Rust ``forensic_report`` kernel. Missing keys default to
# 0.0 so a partial filing still produces a (caveated) verdict.
STANDARD_LINE_ITEMS = (
    "sales",
    "cogs",
    "sga",
    "net_income",
    "cfo",  # cash flow from operations
    "receivables",
    "current_assets",
    "current_liabilities",
    "ppe_net",
    "depreciation",
    "total_assets",
    "total_liabilities",
    "long_term_debt",
    "retained_earnings",
    "ebit",
    "market_cap",
    "shares",
)


def standardize_year(raw: dict[str, Any]) -> dict[str, float]:
    """Coerce a raw financials dict into the engine's standardized schema."""
    out: dict[str, float] = {}
    for key in STANDARD_LINE_ITEMS:
        try:
            out[key] = float(raw.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            out[key] = 0.0
    return out


def forensic_screen(
    this_year: dict[str, Any], prior_year: dict[str, Any]
) -> dict[str, Any]:
    """Run the two-year forensic report. CONCEPT:EX-AHE.harness.ee-25.

    Returns the engine verdict
    ``{m_score, z_score, f_score, accruals_ratio, flags, verdict}`` or
    ``{"error": ...}`` when the engine is unreachable.
    """
    engine = finance_engine()
    if engine is None:
        return {"error": ENGINE_REQUIRED_ERR}

    ty = standardize_year(this_year)
    py = standardize_year(prior_year)
    try:
        report = engine.finance.forensic_report(ty, py)
        return dict(report) if isinstance(report, dict) else {"report": report}
    except Exception as exc:  # noqa: BLE001
        logger.error("forensic_report failed: %s", exc)
        return {"error": str(exc)}
