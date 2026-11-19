"""Polymarket wallet-intelligence tool group — analytics over a synthetic CSV.

Migrated from the former standalone ``poly-wallet-mcp`` test suite. CONCEPT:EX-AHE.harness.ee-27.
"""

import inspect
import json

import pytest

from emerald_exchange.data.wallet_intel import (
    NoDatasetConfigured,
    PolyWalletApi,
    _coerce,
)


# --------------------------------------------------------------------------- #
# Loader / coercion
# --------------------------------------------------------------------------- #
def test_column_aliasing():
    raw = {
        "proxyWallet": "0xABC",
        "usdcSize": "10",
        "taker_direction": "buy",
        "asset_id": "tok",
        "marketId": "m",
    }
    out = _coerce(raw)
    assert out["wallet"] == "0xabc"
    assert out["usd_amount"] == 10.0
    assert out["side"] == "BUY"
    assert out["token"] == "tok"
    assert out["market_id"] == "m"


# --------------------------------------------------------------------------- #
# Analytics over the synthetic dataset (pure-Python, no polars)
# --------------------------------------------------------------------------- #
def test_wallet_profile(trades_csv):
    client = PolyWalletApi(dataset_path=trades_csv)
    p = client.wallet_profile("0xWINNER")
    assert p["found"] is True
    assert p["n_trades"] == 3
    assert p["wins"] == 2
    assert p["decided_positions"] == 3
    assert abs(p["win_rate"] - 0.6667) < 0.01
    # net pnl: m1 +60, m2 +50, m3 -60 = +50
    assert p["total_pnl"] == 50.0


def test_rank_wallets_filters_and_ranks(trades_csv):
    client = PolyWalletApi(dataset_path=trades_csv)
    res = client.rank_wallets(min_trades=3, min_win_rate=0.5, top_k=10)
    wallets = [t["wallet"] for t in res["targets"]]
    assert "0xwinner" in wallets
    assert "0xloser" not in wallets


def test_smart_money_convergence(trades_csv):
    client = PolyWalletApi(dataset_path=trades_csv)
    res = client.smart_money_convergence(
        "tYES", ["0xWINNER", "0xLOSER"], market_id="m1"
    )
    assert res["n_target_wallets"] == 2
    assert res["n_long"] == 1
    assert res["long_convergence"] == 0.5


def test_exit_behavior(trades_csv):
    client = PolyWalletApi(dataset_path=trades_csv)
    res = client.exit_behavior("0xLOSER")
    assert res["found"] is True
    # m4 is an unresolved position that was sold -> exited before resolution
    assert res["pct_exit_before_resolution"] > 0.0


# --------------------------------------------------------------------------- #
# Graceful degradation
# --------------------------------------------------------------------------- #
def test_load_without_dataset_raises_clear_error(monkeypatch):
    monkeypatch.delenv("POLY_TRADES_PATH", raising=False)
    client = PolyWalletApi(dataset_path=None)
    with pytest.raises(NoDatasetConfigured):
        client.load()


def test_missing_file_raises_clear_error():
    client = PolyWalletApi(dataset_path="/nonexistent/path/trades.csv")
    with pytest.raises(NoDatasetConfigured):
        client.load()


# --------------------------------------------------------------------------- #
# Tool shim returns error payload, never crashes
# --------------------------------------------------------------------------- #
def _build_tool():
    from emerald_exchange.mcp.mcp_wallet_intel import register_wallet_intel_tools

    captured = {}

    class _MCP:
        def tool(self, **_kwargs):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

    register_wallet_intel_tools(_MCP())
    return captured


def test_tool_shim_returns_error_payload_not_crash(monkeypatch):
    monkeypatch.delenv("POLY_TRADES_PATH", raising=False)
    import asyncio

    tool = _build_tool()["emerald_wallet_intel_rank_wallets"]
    out = asyncio.run(tool())
    payload = json.loads(out)
    assert payload.get("ok") is False
    assert "error" in payload


def test_tool_one_typed_tool_per_operation():
    tools = _build_tool()
    assert sorted(tools) == [
        "emerald_wallet_intel_exit_behavior",
        "emerald_wallet_intel_rank_wallets",
        "emerald_wallet_intel_smart_money_convergence",
        "emerald_wallet_intel_wallet_profile",
    ]
    for fn in tools.values():
        params = inspect.signature(fn).parameters
        assert "action" not in params and "params_json" not in params


def test_tool_end_to_end_over_csv(trades_csv, monkeypatch):
    """The tool shim runs real analytics when POLY_TRADES_PATH is configured."""
    monkeypatch.setenv("POLY_TRADES_PATH", trades_csv)
    import asyncio

    tool = _build_tool()["emerald_wallet_intel_wallet_profile"]
    out = asyncio.run(tool(wallet="0xWINNER"))
    payload = json.loads(out)
    assert payload["found"] is True
    assert payload["total_pnl"] == 50.0
