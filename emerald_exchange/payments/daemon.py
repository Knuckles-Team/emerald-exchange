"""Launch the bundled wallet runtime daemon (CONN-EMERALD-EXCHANGE-X402-R011.1).

Console script ``emerald-wallet-daemon``. Resolves the vault password and the
encrypted daemon state from secret references, seeds the state file only when
it is absent, then execs the daemon with the password on stdin (a pipe) and an
environment reduced to the runtime's needs. The MCP server never runs this.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scion_sdk.credentials.resolver import CredentialResolver

from emerald_exchange.payments.custody import resolve_daemon_material
from emerald_exchange.payments.refusals import PaymentRefused
from emerald_exchange.payments.service import _state_home
from emerald_exchange.payments.wallet_runtime import DEFAULT_RUST_BIN_DIR

DAEMON_BINARY = "agentpay-daemon"


@dataclass(frozen=True)
class DaemonLaunch:
    argv: list[str]
    env: dict[str, str]
    state_file: Path
    socket: Path
    password: str = field(repr=False)
    seed: bytes | None = field(default=None, repr=False)


def build_daemon_launch(
    payments: Mapping[str, Any],
    *,
    resolver: CredentialResolver | None = None,
    uid: int | None = None,
) -> DaemonLaunch:
    """Resolve the daemon material and build the exact launch (no side effects)."""
    daemon = payments.get("daemon") or {}
    runtime = payments.get("runtime") or {}
    material = resolve_daemon_material(daemon, resolver)
    home = Path(daemon.get("home") or _state_home() / "wallet-runtime-daemon")
    state_file = Path(daemon.get("state_file") or home / "daemon-state.enc")
    socket = Path(runtime.get("daemon_socket") or home / "run" / "daemon.sock")
    binary = str(
        Path(runtime.get("rust_bin_dir") or DEFAULT_RUST_BIN_DIR) / DAEMON_BINARY
    )
    allow = str(daemon.get("allow_uid", os.getuid() if uid is None else uid))
    if not allow.isdigit():
        raise PaymentRefused("PAYMENTS_DAEMON_UID_INVALID")
    argv = [
        binary,
        "--non-interactive",
        "--vault-password-stdin",
        "--state-file",
        str(state_file),
        "--daemon-socket",
        str(socket),
        "--signer-backend",
        "software",
        "--allow-admin-euid",
        allow,
        "--allow-agent-euid",
        allow,
    ]
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "AGENTPAY_HOME": str(home),
    }
    seed = None if state_file.exists() else material.state
    return DaemonLaunch(
        argv=argv,
        env=env,
        state_file=state_file,
        socket=socket,
        password=material.vault_password,
        seed=seed,
    )


def prepare(launch: DaemonLaunch) -> None:
    """Create private directories and write the state seed (0600) when absent."""
    for directory in {
        Path(launch.env["HOME"]),
        launch.state_file.parent,
        launch.socket.parent,
    }:
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
    if launch.seed is not None:
        fd = os.open(launch.state_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, launch.seed)
        finally:
            os.close(fd)


def exec_daemon(
    launch: DaemonLaunch,
    execve: Callable[[str, list[str], dict[str, str]], Any] = os.execve,
) -> Any:
    """Replace this process with the daemon; the password arrives on stdin."""
    read_end, write_end = os.pipe()
    os.write(write_end, launch.password.encode("utf-8") + b"\n")
    os.close(write_end)
    os.dup2(read_end, 0)
    os.close(read_end)
    return execve(launch.argv[0], launch.argv, launch.env)


def _load_payments_config() -> dict[str, Any]:
    from scion_sdk import paths

    path = paths.config_dir() / "config.json"
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")).get("payments") or {})
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    try:
        launch = build_daemon_launch(_load_payments_config())
        prepare(launch)
    except PaymentRefused as refusal:
        print(f"emerald-wallet-daemon: {refusal.code}", file=sys.stderr)
        raise SystemExit(2) from None
    exec_daemon(launch)


if __name__ == "__main__":
    main()
