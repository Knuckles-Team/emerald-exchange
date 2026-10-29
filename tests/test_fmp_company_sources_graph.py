"""Real connector pack pages and replays Alpaca stock bars into EG."""

import asyncio
import hashlib
import sys
from importlib.metadata import version

import pytest
from agent_connector_sdk.adapters.mcp_tool import McpToolSourceAdapter
from agent_connector_sdk.artifacts.pack import build_content_pack
from agent_connector_sdk.artifacts.resources import ResourceArtifactKind
from agent_connector_sdk.artifacts.tools import ToolArtifactKind
from agent_connector_sdk.ingest.live_declaration import load_declaration as declaration
from agent_connector_sdk.manifest.presets import ToolPreset
from agent_connector_sdk.ports.session import TransportEndpoint
from agent_connector_sdk.runner.syncing import SyncTarget, sync_stream
from agent_connector_sdk.sinks.epistemic_graph import EpistemicGraphSink
from agent_connector_sdk.transports.mcp import McpTransport
from epistemic_graph.connector_pack import ConnectorPackClient
from epistemic_graph.generated.connector_pack import PackProducer
from packaging.version import Version

from emerald_exchange import backends
from emerald_exchange.backends import AlpacaBackend
from tests.live_engine import PRINCIPAL, TENANT, live_compute, served_mcp  # noqa: F401
from tests.test_finance_served_graph import (
    CONNECTOR,
    _catalog,
    _mutation_context,
    scoped_client,
)
from tests.test_fmp_company_sources import stub_fmp


async def _exercise(server):
    client = await scoped_client(["*"])
    try:
        context = _mutation_context().model_copy(update={"tenant_id": TENANT})
        key = "stock-bars-test:bind"
        await client._send(
            "ConnectorPack",
            {
                "op": {
                    "op": "bind",
                    "request": {
                        "context": context.model_copy(
                            update={"idempotency_key": key}
                        ).model_dump(mode="json"),
                        "connector": CONNECTOR,
                        "importer": "principal:sha256:"
                        + hashlib.sha256(PRINCIPAL.encode()).hexdigest(),
                    },
                }
            },
            None,
            idempotency_key=key,
        )
        async with McpTransport().session(
            TransportEndpoint(in_process=server)
        ) as session:
            pack = await build_content_pack(
                session,
                connector=CONNECTOR,
                kinds=[ToolArtifactKind(), ResourceArtifactKind()],
            )
            imported = await ConnectorPackClient(client).import_pack(
                pack.archive,
                connector=CONNECTOR,
                server_package_version=pack.server_package_version,
                producer=PackProducer(name="stock-bars-test", version="1"),
                catalog=_catalog(),
                context=context,
            )
            assert imported.result == "imported"

            async def authority(_):
                return _catalog(), context

            for kind in ("profile", "income", "earnings", "logo"):
                source = next(
                    s
                    for s in declaration("emerald_exchange").sources
                    if s.source_id == f"fmp-company-{kind}"
                )
                raw = {
                    **source.preset,
                    "server": CONNECTOR,
                    "tool": source.tools[0],
                    "id_field": source.id_field,
                    "text_field": source.text_field,
                    "title_field": source.title_field,
                    "records_path": source.records_path,
                    "params": {
                        **source.preset["params"],
                        "symbol": "AAPL",
                        "license_tag": "test-license",
                    },
                }
                adapter = McpToolSourceAdapter(
                    ToolPreset.from_mapping(source.source_id, raw),
                    connector=CONNECTOR,
                    mapping_reference=f"connector:{CONNECTOR}#mappings/CompanyRecord",
                )
                target = SyncTarget(
                    CONNECTOR, EpistemicGraphSink(client, authority), max_pages=1
                )
                assert (await sync_stream(session, adapter, target)).records == 1
                assert (await sync_stream(session, adapter, target)).records == 1
        rows = await client.query.cypher_read(
            "MATCH (n) WHERE n.source_stream IS NOT NULL RETURN n LIMIT 100"
        )
        for kind in ("profile", "income", "earnings", "logo"):
            records = [
                r["n"]
                for r in rows
                if r["n"].get("source_stream") == f"fmp-company-{kind}"
            ]
            assert len(records) == 1
            assert records[0]["symbol"] == "AAPL"
        logo = next(
            r["n"] for r in rows if r["n"].get("source_stream") == "fmp-company-logo"
        )
        assert logo["image_media_type"] == "image/png"
    finally:
        await client.close()


@pytest.mark.skipif(
    Version(version("epistemic-graph")) < Version("2.27.6"),
    reason="real connector pack replay requires graph 2.27.6",
)
def test_served_company_sources_reimport_into_graph(live_compute, monkeypatch):  # noqa: F811
    stub_fmp(monkeypatch)
    backend = AlpacaBackend(fmp_api_key="test-key")
    backend.connect = lambda: True
    monkeypatch.setattr(backends, "create_backend", lambda *_: backend)
    monkeypatch.setattr(sys, "argv", ["emerald-exchange", "--transport", "stdio"])
    asyncio.run(_exercise(served_mcp()))
