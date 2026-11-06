"""The bundled wallet runtime CLI as a typed transport (CONN-EMERALD-EXCHANGE-X402-R008.1, R012.1).

Every call is an argument list (no shell) ending in ``--json``. The agent
auth token goes to the CLI on stdin only (``--agent-auth-token-stdin``),
never in argv or the environment, and is scrubbed from every output. The
transport is injectable so tests drive a fake runtime and move no funds.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from emerald_exchange.payments.custody import AgentCredential
from emerald_exchange.payments.refusals import PaymentRefused

DEFAULT_BIN = "/opt/wallet-runtime/bin/wallet-runtime"
DEFAULT_RUST_BIN_DIR = "/opt/wallet-runtime/runtime/bin"
DEFAULT_TIMEOUT_S = 90.0

_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_NETWORK = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_APPROVAL_ID = re.compile(
    r"approval[_ -]?request[_ -]?id\"?\s*[:=]\s*\"?([0-9a-fA-F-]{36})", re.IGNORECASE
)
#: Runtime daemon policy refusals, surfaced by name (never the runtime message).
POLICY_REASONS = (
    "PerTxLimitExceeded",
    "WindowLimitExceeded",
    "AmountExceeded",
    "TxCountLimitExceeded",
    "MaxFeePerGasLimitExceeded",
    "PriorityFeePerGasLimitExceeded",
    "CalldataBytesLimitExceeded",
    "NoAttachedPolicies",
    "NoApplicablePolicies",
    "ManualApprovalRejected",
    "Eip712SigningDenied",
)


@dataclass(frozen=True)
class RuntimeResult:
    returncode: int
    stdout: str
    stderr: str


class RuntimeTransport(Protocol):
    def __call__(
        self,
        argv: Sequence[str],
        *,
        stdin: str,
        env: Mapping[str, str],
        timeout: float,
    ) -> RuntimeResult: ...


class SubprocessTransport:
    """Runs the runtime CLI as a child process."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        stdin: str,
        env: Mapping[str, str],
        timeout: float,
    ) -> RuntimeResult:
        try:
            done = subprocess.run(  # noqa: S603 - fixed argv, no shell
                list(argv),
                input=stdin,
                env=dict(env),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise PaymentRefused("PAYMENTS_RUNTIME_TIMEOUT") from None
        except OSError:
            raise PaymentRefused("PAYMENTS_RUNTIME_MISSING") from None
        return RuntimeResult(done.returncode, done.stdout or "", done.stderr or "")


def require_address(value: str, field: str) -> str:
    if not isinstance(value, str) or not _EVM_ADDRESS.match(value.strip()):
        raise PaymentRefused("PAYMENTS_ADDRESS_INVALID", field=field)
    return value.strip()


def require_network(value: str) -> str:
    if not isinstance(value, str) or not _NETWORK.match(value.strip()):
        raise PaymentRefused("PAYMENTS_NETWORK_INVALID")
    return value.strip()


def require_https(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("https://")
        or any(c.isspace() for c in value)
    ):
        raise PaymentRefused("PAYMENTS_URL_INVALID")
    return value


def _scrub(value: Any, secret: str) -> Any:
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "<redacted>")
    if isinstance(value, list):
        return [_scrub(v, secret) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v, secret) for k, v in value.items()}
    return value


def _parse_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            return None
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            return None


class WalletRuntime:
    """One method per bounded runtime operation."""

    def __init__(
        self,
        *,
        credential: Callable[[], AgentCredential],
        daemon_socket: str,
        home: str | os.PathLike[str],
        binary: str = DEFAULT_BIN,
        rust_bin_dir: str = DEFAULT_RUST_BIN_DIR,
        transport: RuntimeTransport | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        networks: Mapping[str, Any] | None = None,
    ) -> None:
        self._credential = credential
        self.daemon_socket = daemon_socket
        self.home = Path(home)
        self.binary = binary
        self.rust_bin_dir = rust_bin_dir
        self._transport = transport
        self.timeout_s = min(max(float(timeout_s), 5.0), 600.0)
        self.networks = dict(networks or {})

    def available(self) -> bool:
        if self._transport is not None:
            return True
        return os.path.isfile(self.binary) and os.access(self.binary, os.X_OK)

    # -- plumbing ---------------------------------------------------------
    def _prepare_home(self, credential: AgentCredential) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        os.chmod(self.home, 0o700)
        config = {
            "rustBinDir": self.rust_bin_dir,
            "daemonSocket": self.daemon_socket,
            "agentKeyId": credential.key_id,
            "wallet": credential.profile,
        }
        path = self.home / "config.json"
        body = json.dumps(config, indent=2, sort_keys=True)
        if path.exists() and path.read_text(encoding="utf-8") == body:
            return
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.chmod(path, 0o600)

    def _env(self, credential: AgentCredential) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(self.home),
            "LANG": "C.UTF-8",
            "AGENTPAY_HOME": str(self.home),
            "AGENTPAY_DAEMON_SOCKET": self.daemon_socket,
            "AGENTPAY_AGENT_KEY_ID": credential.key_id,
        }

    def run(self, args: Sequence[str], *, agent: bool = True) -> dict[str, Any]:
        """Run one CLI command and return its JSON payload or raise a refusal."""
        if not self.available():
            raise PaymentRefused("PAYMENTS_RUNTIME_MISSING")
        credential = self._credential()
        self._prepare_home(credential)
        transport = self._transport or SubprocessTransport()
        argv = [self.binary, *args, "--json"]
        stdin = ""
        if agent:
            argv.append("--agent-auth-token-stdin")
            stdin = credential.auth_token + "\n"
        result = transport(
            argv, stdin=stdin, env=self._env(credential), timeout=self.timeout_s
        )
        token = credential.auth_token
        out = _scrub(result.stdout, token)
        err = _scrub(result.stderr, token)
        payload = _parse_json(out)
        if result.returncode == 0 and isinstance(payload, dict):
            return _scrub(payload, token)
        combined = f"{out}\n{err}"
        match = _APPROVAL_ID.search(combined)
        if match or "ManualApprovalRequired" in combined:
            return {
                "status": "PENDING_APPROVAL",
                "approval_request_id": match.group(1) if match else "",
            }
        for reason in POLICY_REASONS:
            if reason in combined:
                raise PaymentRefused("WALLET_POLICY_REFUSED", reason=reason)
        raise PaymentRefused("PAYMENTS_RUNTIME_FAILED", exit_code=result.returncode)

    def _rpc_url(self, network: str, rpc_url: str) -> str:
        if rpc_url:
            return require_https(rpc_url)
        entry = self.networks.get(network) or {}
        url = entry.get("rpc_url") if isinstance(entry, Mapping) else None
        if not url:
            raise PaymentRefused("PAYMENTS_RPC_UNSET", network=network)
        return require_https(str(url))

    # -- reads ------------------------------------------------------------
    def wallet(self) -> dict[str, Any]:
        return self.run(["wallet"], agent=False)

    def balance(
        self, network: str, token: str = "", rpc_url: str = ""
    ) -> dict[str, Any]:
        network = require_network(network)
        address = str(self._credential().profile.get("address") or "")
        args = [
            "rpc",
            "balance",
            "--address",
            require_address(address, "wallet.address"),
            "--rpc-url",
            self._rpc_url(network, rpc_url),
        ]
        if token:
            args += ["--token", require_address(token, "token")]
        return self.run(args, agent=False)

    # -- writes (callers pass the governor first) --------------------------
    def transfer_native(self, network: str, to: str, amount: str) -> dict[str, Any]:
        return self.run(
            [
                "transfer-native",
                "--network",
                require_network(network),
                "--to",
                require_address(to, "to"),
                "--amount",
                amount,
                "--broadcast",
            ]
        )

    def transfer_token(
        self, network: str, token: str, to: str, amount: str
    ) -> dict[str, Any]:
        return self.run(
            [
                "transfer",
                "--network",
                require_network(network),
                "--token",
                require_address(token, "token"),
                "--to",
                require_address(to, "to"),
                "--amount",
                amount,
                "--broadcast",
            ]
        )

    def approve(
        self, network: str, token: str, spender: str, amount: str
    ) -> dict[str, Any]:
        return self.run(
            [
                "approve",
                "--network",
                require_network(network),
                "--token",
                require_address(token, "token"),
                "--spender",
                require_address(spender, "spender"),
                "--amount",
                amount,
                "--broadcast",
            ]
        )

    def machine_payment(
        self, url: str, amount: str, method: str = "GET", json_body: str = ""
    ) -> dict[str, Any]:
        method = method.upper()
        if method not in {"GET", "POST"}:
            raise PaymentRefused("PAYMENTS_METHOD_INVALID")
        args = ["mpp", require_https(url), "--amount", amount, "--method", method]
        if json_body:
            try:
                json.loads(json_body)
            except json.JSONDecodeError:
                raise PaymentRefused("PAYMENTS_BODY_INVALID") from None
            args += ["--json-body", json_body]
        return self.run(args)
