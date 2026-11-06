"""The wallet rail: governor first, then the runtime, then one ledger line.

CONN-EMERALD-EXCHANGE-X402-R008.1, R010.1 and R015. Paper is the default;
a paper send records a simulated receipt and calls no runtime.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from scion_sdk import paths
from scion_sdk.credentials.resolver import CredentialResolver

from emerald_exchange.payments.custody import (
    AgentCredential,
    resolve_agent_credential,
)
from emerald_exchange.payments.governor import PaymentGovernor, asset_key
from emerald_exchange.payments.ledger import OrderRecord, PaymentLedger
from emerald_exchange.payments.refusals import PaymentRefused
from emerald_exchange.payments.wallet_runtime import (
    DEFAULT_BIN,
    DEFAULT_RUST_BIN_DIR,
    DEFAULT_TIMEOUT_S,
    RuntimeTransport,
    WalletRuntime,
)
from emerald_exchange.risk_guards import RiskGuard

_TX_KEYS = ("txHash", "transactionHash", "hash", "tx_hash")
_RUNTIME_FAILURES = frozenset({"PAYMENTS_RUNTIME_FAILED", "PAYMENTS_RUNTIME_TIMEOUT"})


def _state_home() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(base)


def _reference(payload: Mapping[str, Any]) -> str:
    for key in _TX_KEYS:
        if payload.get(key):
            return str(payload[key])
    for nested in ("transaction", "broadcast", "result", "payment"):
        inner = payload.get(nested)
        if isinstance(inner, Mapping):
            found = _reference(inner)
            if found:
                return found
    return ""


class WalletService:
    """Governed wallet operations over an optional runtime."""

    def __init__(
        self,
        governor: PaymentGovernor,
        ledger: PaymentLedger,
        runtime: WalletRuntime | None,
    ) -> None:
        self.governor = governor
        self.ledger = ledger
        self.runtime = runtime

    def _runtime(self) -> WalletRuntime:
        if self.runtime is None:
            raise PaymentRefused("PAYMENTS_WALLET_UNSET")
        if not self.runtime.available():
            raise PaymentRefused("PAYMENTS_RUNTIME_MISSING")
        return self.runtime

    # -- reads ------------------------------------------------------------
    def get_wallet(self) -> dict[str, Any]:
        return self._runtime().wallet()

    def get_balance(
        self, network: str, token: str = "", rpc_url: str = ""
    ) -> dict[str, Any]:
        return self._runtime().balance(network, token, rpc_url)

    def get_spend_limits(self) -> dict[str, Any]:
        return self.governor.limits()

    # -- writes -----------------------------------------------------------
    def send(
        self,
        *,
        kind: str,
        network: str,
        token: str,
        amount: str,
        request_id: str,
        call: Callable[[WalletRuntime, str], dict[str, Any]],
    ) -> dict[str, Any]:
        """Admit, run (live) or simulate (paper), and record one wallet send."""
        if not request_id or not request_id.strip():
            raise PaymentRefused("PAYMENTS_REQUEST_ID_REQUIRED")
        request_id = request_id.strip()
        existing = self.ledger.find(request_id)
        if existing is not None:
            return {**existing, "replayed": True}
        asset = asset_key(network, token)
        admission = self.governor.admit(asset, amount)
        normalized = format(admission.amount, "f")
        side = "approve" if kind == "approve" else "send"
        if admission.mode == "paper":
            record = self.ledger.append(
                OrderRecord(
                    venue="wallet",
                    order_id=f"paper-{uuid.uuid4().hex[:12]}",
                    side=side,
                    asset=asset,
                    amount=normalized,
                    status="simulated",
                    mode="paper",
                    request_id=request_id,
                    kind=kind,
                )
            )
            return {**record.as_dict(), "replayed": False}
        runtime = self._runtime()
        try:
            payload = call(runtime, normalized)
        except PaymentRefused as refusal:
            if refusal.code in _RUNTIME_FAILURES:
                status = "timeout" if refusal.code.endswith("TIMEOUT") else "failed"
                self.ledger.append(
                    OrderRecord(
                        venue="wallet",
                        order_id=f"wallet-{uuid.uuid4().hex[:12]}",
                        side=side,
                        asset=asset,
                        amount=normalized,
                        status=status,
                        mode="live",
                        request_id=request_id,
                        kind=kind,
                    )
                )
                self.governor.record_failure()
            raise
        self.governor.record_success()
        reference = _reference(payload)
        status = str(
            payload.get("status") or ("broadcast" if reference else "submitted")
        )
        record = self.ledger.append(
            OrderRecord(
                venue="wallet",
                order_id=reference or f"wallet-{uuid.uuid4().hex[:12]}",
                side=side,
                asset=asset,
                amount=normalized,
                status=status.lower(),
                mode="live",
                request_id=request_id,
                reference=reference,
                kind=kind,
            )
        )
        return {**record.as_dict(), "replayed": False, "runtime": payload}

    def transfer_native(
        self, network: str, to: str, amount: str, request_id: str
    ) -> dict[str, Any]:
        return self.send(
            kind="transfer_native",
            network=network,
            token="",
            amount=amount,
            request_id=request_id,
            call=lambda rt, a: rt.transfer_native(network, to, a),
        )

    def transfer_token(
        self, network: str, token: str, to: str, amount: str, request_id: str
    ) -> dict[str, Any]:
        return self.send(
            kind="transfer_token",
            network=network,
            token=token,
            amount=amount,
            request_id=request_id,
            call=lambda rt, a: rt.transfer_token(network, token, to, a),
        )

    def approve_allowance(
        self, network: str, token: str, spender: str, amount: str, request_id: str
    ) -> dict[str, Any]:
        return self.send(
            kind="approve",
            network=network,
            token=token,
            amount=amount,
            request_id=request_id,
            call=lambda rt, a: rt.approve(network, token, spender, a),
        )

    def pay_machine_payment(
        self,
        url: str,
        network: str,
        token: str,
        amount: str,
        method: str,
        json_body: str,
        request_id: str,
    ) -> dict[str, Any]:
        return self.send(
            kind="machine_payment",
            network=network,
            token=token,
            amount=amount,
            request_id=request_id,
            call=lambda rt, a: rt.machine_payment(url, a, method, json_body),
        )


def build_wallet_service(
    config: Mapping[str, Any],
    risk_guard: RiskGuard,
    *,
    transport: RuntimeTransport | None = None,
    resolver: CredentialResolver | None = None,
) -> WalletService:
    """Compose the ledger, governor and (when ``payments.wallet`` is set) runtime."""
    ledger_path = (
        config.get("ledger_path") or paths.data_dir() / "payments-ledger.jsonl"
    )
    ledger = PaymentLedger(ledger_path)
    governor = PaymentGovernor(risk_guard, ledger, config)
    wallet = config.get("wallet") or {}
    if not wallet:
        return WalletService(governor, ledger, None)
    runtime_cfg = config.get("runtime") or {}
    cached: list[AgentCredential] = []

    def credential() -> AgentCredential:
        if not cached:
            cached.append(resolve_agent_credential(wallet, resolver))
        return cached[0]

    home = runtime_cfg.get("home") or _state_home() / "wallet-runtime"
    runtime = WalletRuntime(
        credential=credential,
        daemon_socket=str(
            runtime_cfg.get("daemon_socket")
            or _state_home() / "wallet-runtime-daemon/run/daemon.sock"
        ),
        home=home,
        binary=str(runtime_cfg.get("bin") or DEFAULT_BIN),
        rust_bin_dir=str(runtime_cfg.get("rust_bin_dir") or DEFAULT_RUST_BIN_DIR),
        transport=transport,
        timeout_s=float(runtime_cfg.get("timeout_s", DEFAULT_TIMEOUT_S)),
        networks=config.get("networks") or {},
    )
    return WalletService(governor, ledger, runtime)
