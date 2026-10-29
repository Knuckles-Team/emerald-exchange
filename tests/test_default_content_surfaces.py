"""CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R001: the server lists its packaged skills, ontology and prompts by default."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

import pytest
from fastmcp import Client

PACKAGE = "emerald_exchange"
ROOT = Path(list(importlib.import_module(PACKAGE).__path__)[0])

pytestmark = pytest.mark.spec("CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT-R001")


def _server():
    from unittest.mock import patch

    from fastmcp import FastMCP

    module = importlib.import_module("emerald_exchange.mcp_server")
    with patch("sys.argv", ["emerald-exchange", "--transport", "stdio"]):
        result = module.get_mcp_instance()
    if isinstance(result, FastMCP):
        return result
    return next(value for value in result if isinstance(value, FastMCP))


async def _listings():
    async with Client(_server()) as client:
        resources = {str(r.uri) for r in await client.list_resources()}
        prompts = {p.name for p in await client.list_prompts()}
    return resources, prompts


def test_default_content_surfaces() -> None:
    resources, prompts = asyncio.run(_listings())
    if list(ROOT.glob("skills/*/SKILL.md")):
        assert any(u.startswith("skill://") for u in resources)
    if list(ROOT.glob("ontology/*.ttl")):
        assert any(u.startswith("ontology://emerald-exchange-mcp/") for u in resources)
    for path in ROOT.glob("prompts/*.json"):
        if not path.name.startswith("_"):
            assert path.stem in prompts
