"""CONN-EMERALD-EXCHANGE-X402-R010.1: server-side spend limits for the wallet rail."""

from __future__ import annotations

import pytest

from emerald_exchange.payments.governor import PaymentGovernor
from emerald_exchange.payments.ledger import OrderRecord, PaymentLedger
from emerald_exchange.payments.refusals import PaymentRefused
from emerald_exchange.payments.service import build_wallet_service
from emerald_exchange.risk_guards import RiskGuard
from tests._payments_fixtures import (
    RECIPIENT,
    TOKEN_CONTRACT,
    FakeRuntime,
    payments_config,
    wallet_env,
)

pytestmark = pytest.mark.spec("CONN-EMERALD-EXCHANGE-X402-R010.1")
TOKEN_ASSET = f"bsc:{TOKEN_CONTRACT.lower()}"


def _code(fn) -> str:
    with pytest.raises(PaymentRefused) as caught:
        fn()
    return caught.value.code


def test_wallet_limits_halt_breaker_and_approval(tmp_path, monkeypatch):
    config = payments_config(tmp_path, live=True)
    guard = RiskGuard()
    ledger = PaymentLedger(config["ledger_path"])
    governor = PaymentGovernor(guard, ledger, config)

    assert governor.mode == "live"
    assert _code(lambda: governor.admit("bsc:native", "0")) == "PAYMENTS_AMOUNT_INVALID"
    assert (
        _code(lambda: governor.admit("bsc:native", "abc")) == "PAYMENTS_AMOUNT_INVALID"
    )
    assert _code(lambda: governor.admit("eth:native", "0.1")) == "SPEND_LIMIT_UNSET"
    assert _code(lambda: governor.admit("bsc:native", "1.5")) == "SPEND_LIMIT_EXCEEDED"
    assert _code(lambda: governor.admit(TOKEN_ASSET, "9")) == "APPROVAL_REQUIRED"
    assert governor.admit(TOKEN_ASSET, "7").amount == 7

    # Trailing-day total is read from the ledger, so it survives a reopen.
    ledger.append(
        OrderRecord("wallet", "a", "send", "bsc:native", "1", "broadcast", "live")
    )
    ledger.append(
        OrderRecord("wallet", "b", "send", "bsc:native", "5", "failed", "live")
    )
    reopened = PaymentGovernor(guard, PaymentLedger(config["ledger_path"]), config)
    assert reopened.admit("bsc:native", "1").amount == 1
    assert _code(lambda: reopened.admit("bsc:native", "1.01")) == "SPEND_LIMIT_EXCEEDED"

    # The shared kill switch refuses first.
    guard.halt("test")
    assert _code(lambda: governor.admit("bsc:native", "0.1")) == "KILL_SWITCH_ACTIVE"
    guard.resume()

    # Live needs both mode and opt-in.
    assert (
        PaymentGovernor(guard, ledger, {**config, "live_opt_in": False}).mode == "paper"
    )


def test_breaker_trips_shared_halt_and_paper_calls_no_runtime(tmp_path, monkeypatch):
    wallet = wallet_env(monkeypatch)
    failing = FakeRuntime(returncode=1, stdout="", stderr="boom")
    guard = RiskGuard()
    service = build_wallet_service(
        payments_config(tmp_path, live=True, wallet=wallet), guard, transport=failing
    )
    assert _code(lambda: service.transfer_native("bsc", RECIPIENT, "0.1", "f1")) == (
        "PAYMENTS_RUNTIME_FAILED"
    )
    assert _code(lambda: service.transfer_native("bsc", RECIPIENT, "0.1", "f2")) == (
        "BREAKER_OPEN"
    )
    assert guard.is_halted
    assert _code(lambda: service.transfer_native("bsc", RECIPIENT, "0.1", "f3")) == (
        "KILL_SWITCH_ACTIVE"
    )

    paper_runtime = FakeRuntime()
    paper = build_wallet_service(
        payments_config(tmp_path / "paper", live=False, wallet=wallet),
        RiskGuard(),
        transport=paper_runtime,
    )
    out = paper.transfer_native("bsc", RECIPIENT, "0.5", "paper-1")
    assert out["mode"] == "paper" and out["status"] == "simulated"
    assert out["order_id"].startswith("paper-")
    assert paper_runtime.calls == []
    assert _code(lambda: paper.transfer_native("bsc", RECIPIENT, "0.5", "")) == (
        "PAYMENTS_REQUEST_ID_REQUIRED"
    )
