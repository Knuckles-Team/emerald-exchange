"""CONN-EMERALD-EXCHANGE-X402-R012.1: the wallet runtime is bundled at a pinned release."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from emerald_exchange.payments.refusals import PaymentRefused
from emerald_exchange.payments.service import build_wallet_service
from emerald_exchange.risk_guards import RiskGuard
from tests._payments_fixtures import RECIPIENT, payments_config, wallet_env

pytestmark = pytest.mark.spec("CONN-EMERALD-EXCHANGE-X402-R012.1")
ROOT = Path(__file__).resolve().parents[1]


def test_runtime_bundle_is_pinned_and_absent_runtime_refuses(tmp_path, monkeypatch):
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    table = pyproject["tool"]["pipelines"]["container"]
    stage = "\n".join(table["extra_stages"])
    assert re.search(r"--checksum=sha256:[0-9a-f]{64}\b", stage)
    assert re.search(
        r"https://github\.com/[\w.-]+/[\w.-]+/releases/download/v\d+\.\d+\.\d+/", stage
    )
    assert "FROM builder-base AS wallet-runtime" in stage
    assert any(
        c.startswith("COPY --from=wallet-runtime ") for c in table["stage_copies"]
    )
    assert "nodejs" in table["runtime_apt"]
    assert "emerald-wallet-daemon" in pyproject["project"]["scripts"]
    # The wheel does not depend on the runtime.
    assert not [
        d for d in pyproject["project"]["dependencies"] if "agentpay" in d.lower()
    ]
    assert not (ROOT / "docker" / "Dockerfile").exists()

    config = payments_config(tmp_path, live=True, wallet=wallet_env(monkeypatch))
    config["runtime"]["bin"] = str(tmp_path / "missing-binary")
    service = build_wallet_service(config, RiskGuard())  # real transport, no binary
    for call in (
        service.get_wallet,
        lambda: service.transfer_native("bsc", RECIPIENT, "0.1", "m1"),
    ):
        with pytest.raises(PaymentRefused) as caught:
            call()
        assert caught.value.code == "PAYMENTS_RUNTIME_MISSING"
