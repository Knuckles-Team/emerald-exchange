"""CONN-EMERALD-EXCHANGE-X402-R011.1: wallet secrets resolve only from references."""

from __future__ import annotations

import base64
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from emerald_exchange.payments.custody import resolve_agent_credential
from emerald_exchange.payments.daemon import DaemonLaunch, build_daemon_launch, prepare
from emerald_exchange.payments.refusals import PaymentRefused
from emerald_exchange.payments.service import build_wallet_service
from emerald_exchange.risk_guards import RiskGuard
from tests._payments_fixtures import (
    KEY_ID,
    RECIPIENT,
    TOKEN,
    payments_config,
    wallet_env,
)

pytestmark = pytest.mark.spec("CONN-EMERALD-EXCHANGE-X402-R011.1")
PASSWORD = "vault-password-SECRET-abc"  # sanitizer:ignore - synthetic fixture, asserted never to leak
STATE = b"\x00encrypted-state\xff"


def _daemon_env(monkeypatch) -> dict:
    monkeypatch.setenv("EE_TEST_VAULT_PASSWORD", PASSWORD)
    monkeypatch.setenv("EE_TEST_STATE", base64.b64encode(STATE).decode())
    monkeypatch.delenv("OPENBAO_ADDR", raising=False)
    return {
        "vault_password_ref": "env://EE_TEST_VAULT_PASSWORD",
        "state_ref": "env://EE_TEST_STATE",
    }


def test_wallet_secrets_resolve_only_from_references(tmp_path, monkeypatch):
    refs = wallet_env(monkeypatch)
    credential = resolve_agent_credential(refs)
    assert credential.key_id == KEY_ID and TOKEN not in repr(credential)

    # A literal value in config is refused before anything resolves.
    for key in refs:
        literal = {**refs, key: "plain-value"}
        with pytest.raises(PaymentRefused) as caught:
            resolve_agent_credential(literal)
        assert caught.value.code == "WALLET_SECRET_REF_INVALID"
        assert "plain-value" not in json.dumps(caught.value.as_result())
    monkeypatch.delenv("EE_TEST_AGENT_TOKEN")
    with pytest.raises(PaymentRefused) as caught:
        resolve_agent_credential(refs)
    assert caught.value.code == "WALLET_SECRET_UNAVAILABLE"
    assert "EE_TEST" not in json.dumps(caught.value.as_result())

    # Wallet unset: live sends refuse.
    unset = build_wallet_service(payments_config(tmp_path, live=True), RiskGuard())
    with pytest.raises(PaymentRefused) as caught:
        unset.transfer_native("bsc", RECIPIENT, "0.1", "u1")
    assert caught.value.code == "PAYMENTS_WALLET_UNSET"

    # Daemon launch: password on stdin only, reduced env, seed only when absent.
    payments = {
        "daemon": {
            **_daemon_env(monkeypatch),
            "home": str(tmp_path / "d"),
            "allow_uid": 10001,
        },
        "runtime": {"daemon_socket": str(tmp_path / "d" / "run" / "daemon.sock")},
    }
    launch = build_daemon_launch(payments)
    assert PASSWORD not in repr(launch) and PASSWORD not in " ".join(launch.argv)
    assert PASSWORD not in json.dumps(launch.env)
    assert set(launch.env) == {"PATH", "HOME", "LANG", "AGENTPAY_HOME"}
    assert launch.argv[0].endswith("/agentpay-daemon")
    assert (
        "--vault-password-stdin" in launch.argv and "--non-interactive" in launch.argv
    )
    assert launch.argv[launch.argv.index("--allow-agent-euid") + 1] == "10001"
    prepare(launch)
    assert launch.state_file.read_bytes() == STATE
    assert stat.S_IMODE(launch.state_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(Path(launch.env["HOME"]).stat().st_mode) == 0o700
    assert stat.S_IMODE(launch.socket.parent.stat().st_mode) == 0o700
    launch.state_file.write_bytes(b"daemon-updated")
    assert build_daemon_launch(payments).seed is None  # never overwrite daemon state

    with pytest.raises(PaymentRefused) as caught:
        build_daemon_launch(
            {"daemon": {**payments["daemon"], "vault_password_ref": PASSWORD}}
        )
    assert caught.value.code == "WALLET_SECRET_REF_INVALID"


def test_exec_daemon_delivers_password_on_stdin(tmp_path):
    out = tmp_path / "stdin.txt"
    envout = tmp_path / "env.txt"
    launch = DaemonLaunch(
        argv=["/bin/sh", "-c", f"cat > {out}; env > {envout}"],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "LANG": "C.UTF-8",
            "AGENTPAY_HOME": str(tmp_path),
        },
        state_file=tmp_path / "s",
        socket=tmp_path / "sock",
        password=PASSWORD,
    )
    script = (
        "import pickle,sys;from emerald_exchange.payments.daemon import exec_daemon;"
        "exec_daemon(pickle.loads(bytes.fromhex(sys.argv[1])))"
    )
    import pickle

    subprocess.run(
        [sys.executable, "-c", script, pickle.dumps(launch).hex()],
        check=True,
        env={**os.environ, "EE_PARENT_SECRET": "leak"},
        timeout=30,
    )
    assert out.read_text() == PASSWORD + "\n"
    child_env = envout.read_text()
    assert "EE_PARENT_SECRET" not in child_env and PASSWORD not in child_env
