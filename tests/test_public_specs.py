"""Check the public specification structure without a live service."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs"
REQUIRED = {"spec.md", "plan.md", "test-spec.md", "tasks.md", "status.json"}
REGISTER = REQUIRED | {"requirements.md"}
DELIVERY = {
    "UNKNOWN", "SPECIFIED", "BUILDING", "BUILT", "LANDED", "CLOSED", "DEFERRED", "REJECTED"
}
ACCEPTANCE = {"NOT_AUDITED", "PENDING", "ACCEPTED", "FAILED"}
PRIVATE_REFERENCE = re.compile(
    r"plans/|gitlab|homelab|/home/|workspace/|\bEH-\d{1,3}\b|\bRF-\d{3}\b", re.IGNORECASE
)


def test_public_spec_scaffold_and_status() -> None:
    assert (SPECS / "README.md").is_file()
    assert (ROOT / ".specify/memory/constitution.md").is_file()
    assert REQUIRED <= {path.name for path in (SPECS / "_template").iterdir()}

    features = [path for path in SPECS.iterdir() if path.is_dir() and path.name != "_template"]
    assert features
    owned_ids: set[str] = set()
    for feature in features:
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", feature.name), feature
        assert REGISTER <= {path.name for path in feature.iterdir()}, feature
        status = json.loads((feature / "status.json").read_text())
        assert status["schema_version"] == 1, feature
        assert status["owner_repo"] == "emerald-exchange", feature
        assert status["spec_id"] not in owned_ids, feature
        owned_ids.add(status["spec_id"])
        entries = status["requirements"]
        assert status["requirement_ids"] == [entry["id"] for entry in entries], feature
        defined = (feature / "requirements.md").read_text()
        for entry in entries:
            assert entry["title"] and entry["delivery_state"] in DELIVERY, entry
            assert isinstance(entry["evidence"], list), entry
            assert f"`{entry['id']}`" in defined, entry
        assert status["delivery_state"] in DELIVERY, feature
        assert status["acceptance_state"] in ACCEPTANCE, feature
        assert isinstance(status["evidence"], list), feature
        assert status["spec_id"] in (feature / "spec.md").read_text(), feature


def test_public_specs_have_no_private_dependencies() -> None:
    for path in SPECS.rglob("*"):
        if path.is_file():
            assert not PRIVATE_REFERENCE.search(path.read_text()), path
