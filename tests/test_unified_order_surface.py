"""CONN-EMERALD-EXCHANGE-X402-R015: one order surface across the exchange venue and the wallet rail."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest

from tests._payments_fixtures import RECIPIENT, payments_config

pytestmark = pytest.mark.spec("CONN-EMERALD-EXCHANGE-X402-R015")


def _served(tmp_path, monkeypatch) -> dict:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = {
        "trading": {"default_exchange": "paper"},
        "payments": payments_config(tmp_path, live=False),
    }
    (config_dir / "config.json").write_text(json.dumps(config))
    monkeypatch.setenv("CONNECTOR_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CONNECTOR_DATA_DIR", str(tmp_path / "data"))
    from emerald_exchange.mcp_server import get_mcp_instance

    monkeypatch.setattr(sys, "argv", [sys.argv[0], "--transport", "stdio"])
    mcp = get_mcp_instance()[0]
    return {tool.name: tool for tool in asyncio.run(mcp.local_provider.list_tools())}


def _call(tool, **kwargs):
    result = tool.fn(**kwargs)
    return asyncio.run(result) if asyncio.iscoroutine(result) else result


def test_place_routes_by_venue_and_lists_one_ledger(tmp_path, monkeypatch):
    tools = _served(tmp_path, monkeypatch)
    for name in (
        "emerald_orders_place",
        "emerald_orders_list",
        "emerald_payments_transfer_native",
    ):
        assert name in tools
    assert "action" not in tools["emerald_orders_place"].parameters["properties"]
    assert tools["emerald_orders_list"].annotations.read_only_hint is True

    place = tools["emerald_orders_place"]
    base = {"order_type": "market", "limit_price": 0.0, "network": "", "to": ""}
    buy = _call(
        place,
        venue="exchange",
        side="buy",
        asset="BTC/USD",
        amount="1",
        request_id="x1",
        **base,
    )
    assert buy["venue"] == "exchange" and buy["mode"] == "paper", buy
    send = _call(
        place,
        venue="wallet",
        side="send",
        asset="native",
        amount="0.5",
        request_id="w1",
        **{**base, "network": "bsc", "to": RECIPIENT},
    )
    assert send["venue"] == "wallet" and send["status"] == "simulated", send
    refused = _call(
        place,
        venue="wallet",
        side="buy",
        asset="native",
        amount="1",
        request_id="w2",
        **base,
    )
    assert refused["error"] == "ORDER_SIDE_UNSUPPORTED"
    replay = _call(
        place,
        venue="exchange",
        side="buy",
        asset="BTC/USD",
        amount="1",
        request_id="x1",
        **base,
    )
    assert replay["replayed"] is True

    listed = _call(tools["emerald_orders_list"], venue="all", limit=50)["orders"]
    assert {(o["venue"], o["request_id"]) for o in listed} == {
        ("exchange", "x1"),
        ("wallet", "w1"),
    }
    assert set(listed[0]) >= {
        "venue",
        "order_id",
        "side",
        "asset",
        "amount",
        "status",
        "mode",
    }
    wallet_only = _call(tools["emerald_orders_list"], venue="wallet", limit=50)[
        "orders"
    ]
    assert [o["request_id"] for o in wallet_only] == ["w1"]
