"""Shared fakes for the wallet tests: env:// secrets and a recording runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from emerald_exchange.payments.wallet_runtime import RuntimeResult

TOKEN = "agent-token-SECRET-1234567890"  # sanitizer:ignore - synthetic fixture token, asserted to never leak
KEY_ID = "00000000-0000-4000-8000-000000000001"
ADDRESS = "0x1111111111111111111111111111111111111111"
RECIPIENT = "0x2222222222222222222222222222222222222222"
TOKEN_CONTRACT = "0x8d0D000Ee44948FC98c9B98A4FA4921476f08B0d"
PROFILE = {"address": ADDRESS, "vaultPublicKey": "04ab", "policyAttachment": "default"}


def wallet_env(monkeypatch) -> dict[str, str]:
    monkeypatch.setenv("EE_TEST_AGENT_KEY_ID", KEY_ID)
    monkeypatch.setenv("EE_TEST_AGENT_TOKEN", TOKEN)
    monkeypatch.setenv("EE_TEST_PROFILE", json.dumps(PROFILE))
    monkeypatch.delenv("OPENBAO_ADDR", raising=False)
    return {
        "agent_key_id_ref": "env://EE_TEST_AGENT_KEY_ID",
        "agent_auth_token_ref": "env://EE_TEST_AGENT_TOKEN",
        "profile_ref": "env://EE_TEST_PROFILE",
    }


@dataclass
class FakeRuntime:
    """Records every call; echoes the stdin token back to prove it is scrubbed."""

    returncode: int = 0
    stdout: str | None = None
    stderr: str = ""
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, argv, *, stdin, env, timeout) -> RuntimeResult:
        self.calls.append({"argv": list(argv), "stdin": stdin, "env": dict(env)})
        out = self.stdout
        if out is None:
            out = json.dumps({"txHash": "0xfeed", "status": "broadcast", "echo": stdin})
        return RuntimeResult(self.returncode, out, self.stderr)


def payments_config(tmp_path, *, live: bool, wallet: dict | None = None) -> dict:
    return {
        "mode": "live" if live else "paper",
        "live_opt_in": live,
        "ledger_path": str(tmp_path / "ledger.jsonl"),
        "limits": {
            "bsc:native": {"per_tx": "1", "daily": "2"},
            f"bsc:{TOKEN_CONTRACT.lower()}": {"per_tx": "10", "daily": "15"},
        },
        "approve_above": {f"bsc:{TOKEN_CONTRACT.lower()}": "8"},
        "breaker_failures": 2,
        "networks": {"bsc": {"rpc_url": "https://rpc.invalid"}},
        "runtime": {
            "home": str(tmp_path / "home"),
            "daemon_socket": str(tmp_path / "run" / "daemon.sock"),
            "bin": "/opt/wallet-runtime/bin/wallet-runtime",
        },
        **({"wallet": wallet} if wallet is not None else {}),
    }
