"""Order and account writes are reachable only through the risk-guarded tools."""

from __future__ import annotations

import asyncio
import sys

from emerald_exchange.exchange_operations import READ_OPERATIONS, ExchangeReadOperations

WRITE_OPERATIONS = ("submit_order", "cancel_order", "connect", "disconnect")


def _served() -> dict:
    from emerald_exchange.mcp_server import get_mcp_instance

    argv = sys.argv
    sys.argv = [argv[0], "--transport", "stdio"]
    try:
        mcp = get_mcp_instance()[0]
    finally:
        sys.argv = argv
    return {tool.name: tool for tool in asyncio.run(mcp.local_provider.list_tools())}


def test_per_operation_surface_is_read_only():
    public = {name for name in dir(ExchangeReadOperations) if not name.startswith("_")}
    assert public == set(READ_OPERATIONS)
    assert not public & set(WRITE_OPERATIONS)


def test_no_unguarded_order_tool_is_served():
    tools = _served()
    for operation in WRITE_OPERATIONS:
        assert f"emerald_exchange_{operation}" not in tools
        assert not [name for name in tools if name.endswith(operation) and "orders" not in name]
    for name in ("emerald_orders_submit", "emerald_orders_cancel", "emerald_orders_halt"):
        assert name in tools


def test_guarded_submit_refuses_while_halted(monkeypatch):
    tools = _served()
    asyncio.run(tools["emerald_orders_halt"].fn(symbol="", side="buy", qty=0.0, order_type="market", limit_price=0.0, order_id=""))
    result = asyncio.run(
        tools["emerald_orders_submit"].fn(symbol="AAPL", side="buy", qty=1.0, order_type="market", limit_price=0.0, order_id="")
    )
    assert "halt" in str(result).lower()
    asyncio.run(tools["emerald_orders_resume"].fn(symbol="", side="buy", qty=0.0, order_type="market", limit_price=0.0, order_id=""))


def test_exchanges_info_operation_is_served_and_read_only():
    tools = _served()
    assert "emerald_exchange_exchanges" in tools


def test_exchanges_reports_backends_active_and_mode():
    from emerald_exchange.backends import BACKEND_REGISTRY

    class Backend:
        name = "paper"
        mode = "paper"

    info = ExchangeReadOperations(Backend()).exchanges()
    assert info == {"available": list(BACKEND_REGISTRY), "active": "paper", "mode": "paper"}
