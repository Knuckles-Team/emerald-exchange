"""SEC EDGAR fundamentals tool group — schema, optional-dep, forensic chain.

Migrated from the former standalone ``edgar-mcp`` test suite. CONCEPT:EE-027.
"""

import importlib.util
import json

import pytest

from emerald_exchange.data.edgar import (
    FORENSIC_YEAR_KEYS,
    TAG_ALIASES,
    EdgarApi,
    EdgarIdentityMissing,
    EdgarNotInstalled,
    _norm,
    _num,
)

EDGAR_AVAILABLE = importlib.util.find_spec("edgar") is not None

# The exact 17-key forensic_report (YearData) schema — must stay drop-in for
# the engine's client.finance.forensic_report.
EXPECTED_KEYS = {
    "sales", "cogs", "sga", "net_income", "cfo", "receivables",
    "current_assets", "current_liabilities", "ppe_net", "depreciation",
    "total_assets", "total_liabilities", "long_term_debt", "retained_earnings",
    "ebit", "market_cap", "shares",
}


# --------------------------------------------------------------------------- #
# standardize_financials schema contract
# --------------------------------------------------------------------------- #
def test_forensic_keys_match_yeardata_schema():
    assert set(FORENSIC_YEAR_KEYS) == EXPECTED_KEYS
    assert len(FORENSIC_YEAR_KEYS) == 17


def test_every_key_has_alias_entry():
    """Each forensic key has an alias list (possibly empty for market_cap)."""
    for k in FORENSIC_YEAR_KEYS:
        assert k in TAG_ALIASES


def test_num_parses_accounting_formats():
    assert _num("1,234") == 1234.0
    assert _num("(500)") == -500.0
    assert _num("$2,000") == 2000.0
    assert _num(None) == 0.0
    assert _num("n/a") == 0.0


def test_norm_strips_to_alnum_lower():
    assert _norm("Total Revenue") == "totalrevenue"
    assert _norm("SG&A") == "sga"


# --------------------------------------------------------------------------- #
# Optional-dependency / graceful degradation
# --------------------------------------------------------------------------- #
def test_missing_edgartools_raises_clear_error():
    """When edgartools is absent, _require_edgar raises EdgarNotInstalled."""
    client = EdgarApi(identity="Test test@example.com")
    if EDGAR_AVAILABLE:
        pytest.skip("edgartools installed; cannot test the missing-dep path")
    with pytest.raises(EdgarNotInstalled):
        client._require_edgar()


def test_missing_identity_raises_when_edgar_present():
    """edgartools present but identity unset → EdgarIdentityMissing."""
    if not EDGAR_AVAILABLE:
        pytest.skip("edgartools not installed; identity path unreachable")
    client = EdgarApi(identity="")
    with pytest.raises(EdgarIdentityMissing):
        client._require_edgar()


def test_tool_returns_error_payload_not_crash():
    """The MCP shim converts optional-dep failures into an error payload."""
    from emerald_exchange.mcp.mcp_fundamentals import register_fundamentals_tools

    captured = {}

    class _MCP:
        def tool(self):
            def deco(fn):
                captured["fn"] = fn
                return fn
            return deco

    register_fundamentals_tools(_MCP())
    tool = captured["fn"]

    import asyncio

    # No identity / no edgartools → standardize action returns {"error", ok:false}
    out = asyncio.run(
        tool(action="standardize", params_json=json.dumps({"ticker": "AAPL"}))
    )
    payload = json.loads(out)
    if EDGAR_AVAILABLE:
        # identity missing path
        assert "error" in payload
    else:
        assert payload.get("ok") is False
        assert "error" in payload


def test_unknown_action_returns_error():
    from emerald_exchange.mcp.mcp_fundamentals import register_fundamentals_tools

    captured = {}

    class _MCP:
        def tool(self):
            def deco(fn):
                captured["fn"] = fn
                return fn
            return deco

    register_fundamentals_tools(_MCP())
    import asyncio

    out = asyncio.run(captured["fn"](action="bogus", params_json="{}"))
    assert "Unknown action" in json.loads(out)["error"]


# --------------------------------------------------------------------------- #
# forensic.py controller schema must equal the standardize output schema
# --------------------------------------------------------------------------- #
def test_forensic_standard_line_items_match_standardize_schema():
    """forensic.py STANDARD_LINE_ITEMS must equal the 17-key standardize schema
    so the controller does not zero-out keys the engine kernel needs."""
    from emerald_exchange.forensic import STANDARD_LINE_ITEMS

    assert set(STANDARD_LINE_ITEMS) == EXPECTED_KEYS


def test_forensic_screen_uses_engine_when_reachable(engine_client):
    """When the engine socket is live, forensic_screen returns a verdict dict.

    The two years use the exact 17-key standardize_financials schema the engine
    forensic_report kernel expects (ppe_net / market_cap / shares).
    """
    from emerald_exchange.forensic import forensic_screen

    this_year = {
        "sales": 1000.0, "cogs": 600.0, "sga": 100.0, "net_income": 100.0,
        "cfo": 120.0, "receivables": 150.0, "current_assets": 800.0,
        "current_liabilities": 400.0, "ppe_net": 500.0, "depreciation": 50.0,
        "total_assets": 2000.0, "total_liabilities": 900.0,
        "long_term_debt": 300.0, "retained_earnings": 400.0, "ebit": 200.0,
        "market_cap": 5000.0, "shares": 1000.0,
    }
    prior_year = dict(this_year, sales=900.0, net_income=90.0)
    report = forensic_screen(this_year, prior_year)
    assert isinstance(report, dict)
    assert "error" not in report
    # the engine returns the four forensic scores + verdict
    assert "verdict" in report
    assert "m_score" in report and "z_score" in report and "f_score" in report
