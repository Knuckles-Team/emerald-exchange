"""Test concept parity between docs/concepts.md and source code. CONCEPT:AU-AHE.assimilation.autonomous-trading-ecosystem"""

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
CONCEPTS_MD = ROOT / "docs" / "concepts.md"
SOURCE_DIR = ROOT / "emerald_exchange"


def _extract_concept_ids_from_docs() -> set[str]:
    """Extract all CONCEPT:EE-* IDs from docs/concepts.md."""
    if not CONCEPTS_MD.exists():
        return set()
    text = CONCEPTS_MD.read_text()
    return set(re.findall(r"CONCEPT:EE-\d+", text))


def _extract_concept_ids_from_source() -> set[str]:
    """Extract all CONCEPT:EE-* IDs from Python source files."""
    ids = set()
    for py_file in SOURCE_DIR.rglob("*.py"):
        text = py_file.read_text()
        ids.update(re.findall(r"CONCEPT:EE-\d+", text))
    return ids


def test_concepts_md_exists():
    """docs/concepts.md must exist."""
    assert CONCEPTS_MD.exists(), "docs/concepts.md is missing"


def test_concept_prefix_unique():
    """Ensure CONCEPT:EE-* prefix is used (no collisions with other projects)."""
    doc_ids = _extract_concept_ids_from_docs()
    assert all(cid.startswith("CONCEPT:EE-") for cid in doc_ids)


def test_source_concepts_documented():
    """Every CONCEPT:EE-* in source code should appear in docs/concepts.md."""
    doc_ids = _extract_concept_ids_from_docs()
    src_ids = _extract_concept_ids_from_source()
    undocumented = src_ids - doc_ids
    assert not undocumented, f"Undocumented concept IDs in source: {undocumented}"


def test_eco_bridge_reference():
    """docs/concepts.md must reference CONCEPT:AU-ECO.messaging.native-backend-abstraction bridge."""
    text = CONCEPTS_MD.read_text()
    assert "AU-ECO.messaging.native-backend-abstraction" in text, "Missing CONCEPT:AU-ECO.messaging.native-backend-abstraction bridge reference"
