"""SEC EDGAR fundamentals provider — CONCEPT:EX-AHE.harness.ee-26.

Folded into emerald-exchange from the former standalone ``edgar-mcp`` package so
the unified finance hub can feed agents *real* SEC filings instead of
hallucinated numbers:

* **Filings** — latest N filings of a given form (10-K, 10-Q, 8-K, ...).
* **Financials** — standardized income / balance / cash-flow statements.
* **Narrative** — Risk Factors (Item 1A) and MD&A (Item 7), this year + prior
  year, for diffing.
* **Full-text search** — the EDGAR phrase search (e.g. "material weakness").
* **standardize_financials** — maps a company's two latest fiscal years into the
  exact 17-key dict schema consumed by epistemic-graph ``forensic_report``.

``edgartools`` is an *optional* dependency. Importing this module must never
hard-fail when it is absent, so the actual import is deferred to
``_require_edgar()`` which raises a clear, actionable error at call time. The SEC
identity is read from ``EDGAR_IDENTITY`` (or legacy ``EDGAR_USER_AGENT``).
"""

from __future__ import annotations

import os
from typing import Any

# The exact 17-key schema consumed by epistemic-graph forensic_report (YearData).
FORENSIC_YEAR_KEYS: tuple[str, ...] = (
    "sales",
    "cogs",
    "sga",
    "net_income",
    "cfo",
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
# Back-compat alias used by the standardize_financials machinery.
FORENSIC_KEYS = FORENSIC_YEAR_KEYS


# ---------------------------------------------------------------------------- #
# Tag aliasing — the article's ``g()`` helper, generalized.
#
# US-GAAP / standardized statements expose the same economic line item under
# several labels across filers and years. Each forensic_report key maps to an
# ordered list of candidate labels; the first that resolves wins (best effort).
# ---------------------------------------------------------------------------- #
TAG_ALIASES: dict[str, list[str]] = {
    "sales": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "TotalRevenue",
        "Revenue",
        "Total revenue",
        "Net sales",
        "Net revenue",
    ],
    "cogs": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
        "Cost of revenue",
        "Cost of goods sold",
        "Cost of sales",
    ],
    "sga": [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
        "OperatingExpenses",
        "Selling, general and administrative",
        "SG&A",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "Net income",
        "Net income (loss)",
        "Net earnings",
    ],
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "Net cash provided by operating activities",
        "Cash from operations",
        "Operating cash flow",
    ],
    "receivables": [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        "Accounts receivable, net",
        "Accounts receivable",
    ],
    "current_assets": [
        "AssetsCurrent",
        "Total current assets",
        "Current assets",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
        "Total current liabilities",
        "Current liabilities",
    ],
    "ppe_net": [
        "PropertyPlantAndEquipmentNet",
        "Property, plant and equipment, net",
        "Property and equipment, net",
        "PP&E, net",
    ],
    "depreciation": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
        "Depreciation and amortization",
    ],
    "total_assets": [
        "Assets",
        "Total assets",
    ],
    "total_liabilities": [
        "Liabilities",
        "Total liabilities",
    ],
    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "Long-term debt",
        "Long term debt",
    ],
    "retained_earnings": [
        "RetainedEarningsAccumulatedDeficit",
        "Retained earnings",
        "Retained earnings (accumulated deficit)",
    ],
    "ebit": [
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeInterestExpenseInterestIncomeIncomeTaxesExtraordinaryItemsNoncontrollingInterestsNet",
        "Operating income",
        "Operating income (loss)",
        "EBIT",
    ],
    "market_cap": [],  # not a statement line item; computed/best-effort
    "shares": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "CommonStockSharesOutstanding",
        "Weighted average shares outstanding",
        "Shares outstanding",
    ],
}


class EdgarNotInstalled(RuntimeError):
    """Raised when an EDGAR operation needs ``edgartools`` but it is missing."""


class EdgarIdentityMissing(RuntimeError):
    """Raised when the SEC identity header is not configured."""


class EdgarApi:
    """Full client for SEC EDGAR via the optional ``edgartools`` package.

    The SEC requires a descriptive ``User-Agent`` (an identity string of the
    form ``"Name email@example.com"``). It is read from ``EDGAR_IDENTITY`` (or
    the legacy ``EDGAR_USER_AGENT``) and set on the ``edgar`` module the first
    time the library is needed.
    """

    def __init__(self, identity: str | None = None) -> None:
        self.identity = (
            identity or os.getenv("EDGAR_IDENTITY") or os.getenv("EDGAR_USER_AGENT", "")
        )
        self._edgar: Any | None = None

    # ------------------------------------------------------------------ #
    # Lazy import / identity plumbing
    # ------------------------------------------------------------------ #
    def _require_edgar(self) -> Any:
        """Import ``edgar`` lazily and configure the SEC identity header.

        Returns the imported ``edgar`` module. Raises a clear error rather than
        crashing on import when the optional dependency is absent or the SEC
        identity is unset.
        """
        if self._edgar is not None:
            return self._edgar
        try:
            import edgar  # type: ignore
        except Exception as exc:  # ImportError or transitive failure
            raise EdgarNotInstalled(
                "edgartools is not installed. Install it with "
                "`pip install 'emerald-exchange[fundamentals]'` "
                "(or `pip install edgartools`)."
            ) from exc
        if not self.identity:
            raise EdgarIdentityMissing(
                "SEC EDGAR requires an identity header. Set the EDGAR_IDENTITY "
                "environment variable, e.g. EDGAR_IDENTITY='Jane Doe jane@example.com'."
            )
        try:
            edgar.set_identity(self.identity)
        except Exception:
            # Older/newer edgartools may expose identity differently; best effort.
            pass
        self._edgar = edgar
        return edgar

    @property
    def available(self) -> bool:
        """True if ``edgartools`` can be imported (does not require identity)."""
        try:
            import edgar  # noqa: F401  # type: ignore

            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Company / filings
    # ------------------------------------------------------------------ #
    def _company(self, ticker_or_cik: str) -> Any:
        edgar = self._require_edgar()
        return edgar.Company(ticker_or_cik)

    def fetch_filings(
        self,
        ticker_or_cik: str,
        form: str = "10-K",
        latest: int = 5,
    ) -> dict[str, Any]:
        """Return metadata for the latest ``latest`` filings of ``form``."""
        company = self._company(ticker_or_cik)
        filings = company.get_filings(form=form)
        latest_set = filings.latest(latest) if hasattr(filings, "latest") else filings
        # ``latest`` returns either a single filing or an iterable.
        items = latest_set if hasattr(latest_set, "__iter__") else [latest_set]
        out = []
        for f in items:
            out.append(
                {
                    "form": getattr(f, "form", form),
                    "filing_date": str(getattr(f, "filing_date", "")),
                    "accession_no": getattr(f, "accession_no", None)
                    or getattr(f, "accession_number", None),
                    "company": getattr(f, "company", None),
                    "cik": getattr(f, "cik", None),
                    "url": getattr(f, "homepage_url", None) or getattr(f, "url", None),
                }
            )
        return {
            "ticker": ticker_or_cik,
            "form": form,
            "count": len(out),
            "filings": out,
        }

    # ------------------------------------------------------------------ #
    # Financial statements
    # ------------------------------------------------------------------ #
    def get_financials(
        self,
        ticker_or_cik: str,
        statement: str = "income",
    ) -> dict[str, Any]:
        """Return a standardized statement as ``{label: {period: value}}``.

        ``statement`` is one of ``income``, ``balance``, ``cashflow``.
        """
        company = self._company(ticker_or_cik)
        fin = (
            company.get_financials()
            if hasattr(company, "get_financials")
            else (company.financials)
        )
        stmt = self._select_statement(fin, statement)
        return {
            "ticker": ticker_or_cik,
            "statement": statement,
            "data": self._statement_to_dict(stmt),
        }

    @staticmethod
    def _select_statement(fin: Any, statement: str) -> Any:
        key = statement.lower()
        if key in ("income", "income_statement", "is"):
            for attr in ("income_statement", "income"):
                if hasattr(fin, attr):
                    obj = getattr(fin, attr)
                    return obj() if callable(obj) else obj
        elif key in ("balance", "balance_sheet", "bs"):
            for attr in ("balance_sheet", "balance"):
                if hasattr(fin, attr):
                    obj = getattr(fin, attr)
                    return obj() if callable(obj) else obj
        elif key in ("cashflow", "cash_flow", "cash_flow_statement", "cf"):
            for attr in ("cashflow_statement", "cash_flow_statement", "cashflow"):
                if hasattr(fin, attr):
                    obj = getattr(fin, attr)
                    return obj() if callable(obj) else obj
        raise ValueError(
            f"Unknown statement {statement!r} (use income/balance/cashflow)."
        )

    @staticmethod
    def _statement_to_dict(stmt: Any) -> dict[str, Any]:
        """Best-effort serialization of an edgartools statement to a dict."""
        # edgartools statements usually expose a pandas DataFrame via .to_dataframe()
        for attr in ("to_dataframe", "to_pandas"):
            if hasattr(stmt, attr):
                try:
                    df = getattr(stmt, attr)()
                    return {
                        str(k): _row_to_dict(v) for k, v in df.to_dict("index").items()
                    }
                except Exception:
                    break
        if hasattr(stmt, "to_dict"):
            try:
                return stmt.to_dict()
            except Exception:
                pass
        return {"repr": str(stmt)}

    # ------------------------------------------------------------------ #
    # Narrative items (Risk Factors / MD&A), this year + prior year
    # ------------------------------------------------------------------ #
    def _two_latest_10k(self, ticker_or_cik: str) -> list[Any]:
        company = self._company(ticker_or_cik)
        filings = company.get_filings(form="10-K")
        latest = filings.latest(2) if hasattr(filings, "latest") else filings
        items = latest if hasattr(latest, "__iter__") else [latest]
        return list(items)[:2]

    def _extract_item(self, ticker_or_cik: str, item: str) -> dict[str, Any]:
        years = self._two_latest_10k(ticker_or_cik)
        out: dict[str, Any] = {"ticker": ticker_or_cik, "item": item, "years": []}
        for f in years:
            text = ""
            try:
                obj = f.obj() if hasattr(f, "obj") else f
                # edgartools 10-K objects support item access by section name.
                if hasattr(obj, "__getitem__"):
                    try:
                        text = str(obj[item])
                    except Exception:
                        text = ""
                if not text and hasattr(obj, item.lower().replace(" ", "_")):
                    text = str(getattr(obj, item.lower().replace(" ", "_")))
            except Exception as exc:
                text = f"<extraction failed: {exc}>"
            out["years"].append(
                {
                    "filing_date": str(getattr(f, "filing_date", "")),
                    "accession_no": getattr(f, "accession_no", None),
                    "text": text,
                }
            )
        return out

    def get_risk_factors(self, ticker_or_cik: str) -> dict[str, Any]:
        """Item 1A Risk Factors, this year + prior year (for diffing)."""
        return self._extract_item(ticker_or_cik, "Item 1A")

    def get_mdna(self, ticker_or_cik: str) -> dict[str, Any]:
        """Item 7 MD&A, this year + prior year (for diffing)."""
        return self._extract_item(ticker_or_cik, "Item 7")

    # ------------------------------------------------------------------ #
    # Full-text search
    # ------------------------------------------------------------------ #
    def full_text_search(
        self, query: str, forms: str | None = None, limit: int = 20
    ) -> dict[str, Any]:
        """EDGAR full-text phrase search (e.g. "material weakness")."""
        edgar = self._require_edgar()
        kwargs: dict[str, Any] = {}
        if forms:
            kwargs["forms"] = [f.strip() for f in forms.split(",") if f.strip()]
        results = (
            edgar.find(query, **kwargs)
            if hasattr(edgar, "find")
            else (edgar.full_text_search(query, **kwargs))
        )
        rows = list(results)[:limit] if hasattr(results, "__iter__") else [results]
        out = []
        for r in rows:
            out.append(
                {
                    "form": getattr(r, "form", None),
                    "filing_date": str(getattr(r, "filing_date", "")),
                    "company": getattr(r, "company", None),
                    "cik": getattr(r, "cik", None),
                    "accession_no": getattr(r, "accession_no", None),
                }
            )
        return {"query": query, "count": len(out), "results": out}

    # ------------------------------------------------------------------ #
    # standardize_financials → forensic_report schema
    # ------------------------------------------------------------------ #
    def standardize_financials(self, ticker_or_cik: str) -> dict[str, Any]:
        """Map the two latest fiscal years into the forensic_report schema.

        Returns ``{"ticker", "periods", "this_year": {...17 keys...},
        "prior_year": {...17 keys...}}`` ready to hand to
        ``epistemic_graph.finance.forensic_report``.
        """
        company = self._company(ticker_or_cik)
        fin = (
            company.get_financials()
            if hasattr(company, "get_financials")
            else (company.financials)
        )

        # Build a flat {label -> [values by period, newest first]} index across
        # all three statements, so tag aliasing can resolve any line item.
        index = self._flatten_financials(fin)
        periods = self._period_order(fin)

        def g(key: str, period_idx: int) -> float:
            """Resolve a forensic key for a given period via alias fallback."""
            for alias in TAG_ALIASES.get(key, []):
                series = index.get(_norm(alias))
                if series is None:
                    continue
                if period_idx < len(series) and series[period_idx] is not None:
                    return _num(series[period_idx])
            return 0.0

        market_cap = self._best_effort_market_cap(company)

        def year(period_idx: int) -> dict[str, float]:
            d = {k: g(k, period_idx) for k in FORENSIC_KEYS}
            if d.get("market_cap", 0.0) == 0.0 and market_cap:
                d["market_cap"] = market_cap
            return d

        return {
            "ticker": ticker_or_cik,
            "periods": periods[:2],
            "this_year": year(0),
            "prior_year": year(1),
        }

    # -- helpers for standardize_financials ----------------------------- #
    @staticmethod
    def _flatten_financials(fin: Any) -> dict[str, list[Any]]:
        index: dict[str, list[Any]] = {}
        for stmt_name in (
            "income_statement",
            "balance_sheet",
            "cashflow_statement",
            "cash_flow_statement",
            "income",
            "balance",
            "cashflow",
        ):
            if not hasattr(fin, stmt_name):
                continue
            obj = getattr(fin, stmt_name)
            stmt = obj() if callable(obj) else obj
            df = None
            for attr in ("to_dataframe", "to_pandas"):
                if hasattr(stmt, attr):
                    try:
                        df = getattr(stmt, attr)()
                        break
                    except Exception:
                        df = None
            if df is None:
                continue
            try:
                cols = list(df.columns)
                for label, row in df.iterrows():
                    values = [row[c] for c in cols]
                    index.setdefault(_norm(str(label)), values)
            except Exception:
                continue
        return index

    @staticmethod
    def _period_order(fin: Any) -> list[str]:
        for stmt_name in ("income_statement", "income", "balance_sheet", "balance"):
            if not hasattr(fin, stmt_name):
                continue
            obj = getattr(fin, stmt_name)
            stmt = obj() if callable(obj) else obj
            for attr in ("to_dataframe", "to_pandas"):
                if hasattr(stmt, attr):
                    try:
                        df = getattr(stmt, attr)()
                        return [str(c) for c in df.columns]
                    except Exception:
                        continue
        return []

    @staticmethod
    def _best_effort_market_cap(company: Any) -> float:
        for attr in ("market_cap", "marketcap"):
            if hasattr(company, attr):
                try:
                    return _num(getattr(company, attr))
                except Exception:
                    pass
        return 0.0


# ---------------------------------------------------------------------------- #
# Module-level helpers
# ---------------------------------------------------------------------------- #
def _norm(label: str) -> str:
    return "".join(ch for ch in label.lower() if ch.isalnum())


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        s = str(v).replace(",", "").replace("$", "").replace("%", "").strip()
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        try:
            return float(s)
        except ValueError:
            return 0.0


def _row_to_dict(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): val for k, val in v.items()}
    return v
