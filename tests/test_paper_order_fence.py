"""The dedicated paper tool refuses live mode and replays without an effect."""

import json

from emerald_exchange.backends import TradingMode
from emerald_exchange.mcp.mcp_orders import register_order_tools


class CaptureMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, **kwargs: object):
        def capture(function: object) -> object:
            self.tools[function.__name__] = function
            return function

        return capture


class Backend:
    def __init__(self, mode: TradingMode) -> None:
        self.mode = mode

    def submit_order(self, *args: object) -> None:
        raise AssertionError("test must never place an order")

    def cancel_order(self, *args: object) -> None:
        raise AssertionError("test must never cancel an order")


def tool(mode: TradingMode):
    capture = CaptureMCP()
    register_order_tools(capture, Backend(mode), object())
    return capture.tools["emerald_paper_orders"]


def test_paper_tool_cannot_reach_live_backend() -> None:
    paper = tool(TradingMode.LIVE)
    result = json.loads(
        paper(action="submit", request_id="request-123", symbol="SOL", qty=1)
    )
    assert result["status"] == "refused"
    assert "paper mode" in result["error"]


def test_paper_tool_requires_bounded_request_id() -> None:
    paper = tool(TradingMode.PAPER)
    result = json.loads(paper(action="submit", request_id="x", symbol="SOL", qty=1))
    assert result["status"] == "refused"


def test_same_request_replays_validation_and_changed_payload_refuses() -> None:
    paper = tool(TradingMode.PAPER)
    first = paper(action="submit", request_id="request-123", symbol="", qty=0)
    assert json.loads(first)["error"] == "symbol and qty > 0 required"
    assert paper(action="submit", request_id="request-123", symbol="", qty=0) == first
    conflict = json.loads(
        paper(action="submit", request_id="request-123", symbol="SOL", qty=1)
    )
    assert conflict == {"status": "refused", "error": "request id conflict"}
