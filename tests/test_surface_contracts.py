"""Connector surface: contracts, links, prompts and ontology roll-up (CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R004)."""

from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "emerald_exchange"

pytestmark = pytest.mark.spec("CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R004")


def test_served_surface_has_no_contract_link_or_prompt_gap() -> None:
    from scion_sdk.testing.surface_check import surface_check

    assert surface_check("emerald_exchange") == []


def test_every_ontology_class_rolls_up_to_core() -> None:
    from scion_sdk.testing.ontology_rollup import orphan_classes

    for ttl in sorted((PACKAGE / "ontology").glob("*.ttl")):
        assert "owl:imports" not in ttl.read_text(encoding="utf-8"), ttl.name
        assert orphan_classes(ttl) == set(), ttl.name
