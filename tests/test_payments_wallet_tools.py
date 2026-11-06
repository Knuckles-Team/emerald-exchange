"""CONN-EMERALD-EXCHANGE-X402-R008.1: one typed tool per wallet-runtime operation."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastmcp import FastMCP

from emerald_exchange.mcp.mcp_payments import register_payments_tools
from emerald_exchange.payments.service import build_wallet_service
from emerald_exchange.risk_guards import RiskGuard
from tests._payments_fixtures import (
    RECIPIENT,
    TOKEN,
    TOKEN_CONTRACT,
    FakeRuntime,
    payments_config,
    wallet_env,
)

pytestmark = pytest.mark.spec("CONN-EMERALD-EXCHANGE-X402-R008.1")

READS = {
    "emerald_payments_get_wallet",
    "emerald_payments_get_balance",
    "emerald_payments_get_spend_limits",
}
WRITES = {
    "emerald_payments_transfer_native",
    "emerald_payments_transfer_token",
    "emerald_payments_approve_allowance",
    "emerald_payments_pay_machine_payment",
}


def _tools(service):
    mcp = FastMCP("t")
    register_payments_tools(mcp, service)
    return {t.name: t for t in asyncio.run(mcp.local_provider.list_tools())}


def test_one_typed_tool_per_wallet_operation(tmp_path, monkeypatch):
    fake = FakeRuntime()
    config = payments_config(tmp_path, live=True, wallet=wallet_env(monkeypatch))
    service = build_wallet_service(config, RiskGuard(), transport=fake)
    tools = _tools(service)

    assert set(tools) == READS | WRITES
    for name, tool in tools.items():
        props = (tool.parameters or {}).get("properties", {})
        assert "action" not in props and "params_json" not in props, name
        assert tool.annotations.read_only_hint is (name in READS), name
    for name in WRITES:
        assert "request_id" in tools[name].parameters["required"], name

    native = tools["emerald_payments_transfer_native"].fn(
        network="bsc", to=RECIPIENT, amount="0.5", request_id="r-native"
    )
    token = tools["emerald_payments_transfer_token"].fn(
        network="bsc",
        token=TOKEN_CONTRACT,
        to=RECIPIENT,
        amount="2",
        request_id="r-token",
    )
    allowance = tools["emerald_payments_approve_allowance"].fn(
        network="bsc",
        token=TOKEN_CONTRACT,
        spender=RECIPIENT,
        amount="1",
        request_id="r-approve",
    )
    machine = tools["emerald_payments_pay_machine_payment"].fn(
        url="https://pay.example/api",
        network="bsc",
        token=TOKEN_CONTRACT,
        amount="0.25",
        request_id="r-mpp",
        method="POST",
        json_body='{"q": 1}',
    )

    argvs = [c["argv"][1:] for c in fake.calls]
    assert argvs[0][:5] == ["transfer-native", "--network", "bsc", "--to", RECIPIENT]
    assert argvs[1][:3] == ["transfer", "--network", "bsc"]
    assert argvs[2][0] == "approve" and "--spender" in argvs[2]
    assert argvs[3][:5] == [
        "mpp",
        "https://pay.example/api",
        "--amount",
        "0.25",
        "--method",
    ]
    for call in fake.calls:
        assert call["argv"][-2:] == ["--json", "--agent-auth-token-stdin"]
        assert call["stdin"] == TOKEN + "\n"
        assert TOKEN not in " ".join(call["argv"])
        assert TOKEN not in json.dumps(call["env"])
        assert "--broadcast" in call["argv"] or call["argv"][1] == "mpp"
    for result in (native, token, allowance, machine):
        assert result["status"] == "broadcast" and result["mode"] == "live"
        assert TOKEN not in json.dumps(result)

    # Replayed request id: recorded entry, no second runtime call.
    again = tools["emerald_payments_transfer_native"].fn(
        network="bsc", to=RECIPIENT, amount="0.5", request_id="r-native"
    )
    assert again["replayed"] is True and len(fake.calls) == 4

    # Reads go to the runtime without the agent token.
    tools["emerald_payments_get_wallet"].fn()
    tools["emerald_payments_get_balance"].fn(network="bsc", token="", rpc_url="")
    assert fake.calls[-2]["argv"][1:] == ["wallet", "--json"]
    assert fake.calls[-1]["argv"][1:4] == ["rpc", "balance", "--address"]
    assert fake.calls[-1]["stdin"] == ""


def test_runtime_queue_and_policy_refusals_surface_by_code(tmp_path, monkeypatch):
    config = payments_config(tmp_path, live=True, wallet=wallet_env(monkeypatch))
    pending = FakeRuntime(
        returncode=3,
        stdout="",
        stderr='ManualApprovalRequired approval_request_id: "123e4567-e89b-42d3-a456-426614174000"',
    )
    tools = _tools(build_wallet_service(config, RiskGuard(), transport=pending))
    out = tools["emerald_payments_transfer_native"].fn(
        network="bsc", to=RECIPIENT, amount="0.1", request_id="p1"
    )
    assert out["status"] == "pending_approval"

    refused = FakeRuntime(
        returncode=1, stdout="", stderr=f"WindowLimitExceeded {TOKEN}"
    )
    tools = _tools(build_wallet_service(config, RiskGuard(), transport=refused))
    out = tools["emerald_payments_transfer_native"].fn(
        network="bsc", to=RECIPIENT, amount="0.1", request_id="p2"
    )
    assert out == {
        "error": "WALLET_POLICY_REFUSED",
        "approved": False,
        "reason": "WindowLimitExceeded",
    }

    bad = tools["emerald_payments_transfer_native"].fn(
        network="bsc", to="not-an-address", amount="0.1", request_id="p3"
    )
    assert bad["error"] == "PAYMENTS_ADDRESS_INVALID"
