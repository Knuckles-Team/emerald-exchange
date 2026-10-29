"""Replay served multi-asset provider fixtures through a real graph."""

import asyncio
import hashlib
import sys
from importlib.metadata import version

import pytest
from agent_connector_sdk.adapters.mcp_tool import McpToolSourceAdapter
from agent_connector_sdk.artifacts.pack import build_content_pack
from agent_connector_sdk.artifacts.resources import ResourceArtifactKind
from agent_connector_sdk.artifacts.tools import ToolArtifactKind
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
from agent_connector_sdk.ingest.live_declaration import load_declaration as declaration
from emerald_exchange.mcp_server import get_mcp_instance
from tests.live_engine import PRINCIPAL, TENANT
from tests.live_engine import live_compute as _live_compute
from tests.test_finance_served_graph import (
    CONNECTOR,
    _catalog,
    _mutation_context,
    scoped_client,
)
from tests.test_multi_asset_sources import stub_providers


@pytest.fixture
def multi_asset_live_compute(tmp_path_factory):
    yield from _live_compute.__wrapped__(tmp_path_factory)


async def _exercise(server, *, validate=False):
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

            for kind in ("fx", "commodity", "commodity_spot", "real_estate"):
                source = next(
                    s
                    for s in declaration("emerald_exchange").sources
                    if s.source_id == f"multi-asset-{kind}"
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
                        "license_tag": "test-license",
                        "tenant_id": TENANT,
                        "source_id": f"multi-asset-{kind}",
                        **(
                            {"base": "EUR", "quote": "USD"}
                            if kind == "fx"
                            else {"attom_id": 123, "max_age_days": 30}
                            if kind == "real_estate"
                            else {}
                            if kind == "commodity_spot"
                            else {
                                "dataset": "GLBX.MDP3",
                                "symbol": "GCZ4",
                                "start": "2024-01-01T00:00:00Z",
                                "end": "2024-01-02T00:00:00Z",
                            }
                        ),
                    },
                }
                adapter = McpToolSourceAdapter(
                    ToolPreset.from_mapping(source.source_id, raw),
                    connector=CONNECTOR,
                    mapping_reference=f"connector:{CONNECTOR}#mappings/MultiAssetRecord",
                )
                if validate:
                    from agent_connector_sdk.finance.multi_asset_source import (
                        MultiAssetKind,
                        MultiAssetSourceAdapter,
                    )

                    adapter = MultiAssetSourceAdapter(
                        adapter,
                        asset_kind=MultiAssetKind(
                            "commodity" if kind == "commodity_spot" else kind
                        ),
                        tenant_id=TENANT,
                        source_id=source.source_id,
                        real_estate_max_age_days=30 if kind == "real_estate" else None,
                    )
                target = SyncTarget(
                    CONNECTOR, EpistemicGraphSink(client, authority), max_pages=1
                )
                assert (await sync_stream(session, adapter, target)).records == 1
                assert (await sync_stream(session, adapter, target)).records == 1
        rows = await client.query.cypher_read(
            "MATCH (n) WHERE n.source_stream IS NOT NULL RETURN n LIMIT 100"
        )
        for kind in ("fx", "commodity", "commodity_spot", "real_estate"):
            records = [
                r["n"]
                for r in rows
                if r["n"].get("source_stream") == f"multi-asset-{kind}"
            ]
            assert len(records) == 1
            assert records[0]["instrument_id"]
            if kind == "fx":
                assert records[0]["base_currency"] == "EUR"
                assert records[0]["quote_currency"] == "USD"
                assert records[0]["rate"] == 1.12
            elif kind == "commodity":
                assert records[0]["basis"] == "future"
                assert records[0]["contract_code"] == "GCZ4"
                assert records[0]["roll_rule"] == "none:fixed-contract"
                assert records[0]["expiry"].startswith("2024-12-01")
            elif kind == "commodity_spot":
                assert records[0]["basis"] == "spot"
                assert records[0]["price"] == 2020.25
                assert records[0]["currency"] == "USD"
            else:
                assert records[0]["valuation_date"].startswith("2024-01-01")
                assert records[0]["stale"] is True
                assert records[0]["estimated_value"] == 500000
    finally:
        await client.close()


@pytest.mark.skipif(
    Version(version("epistemic-graph")) < Version("2.27.6"),
    reason="real connector pack replay requires graph 2.27.6",
)
def test_served_multi_asset_sources_reimport_into_graph(
    multi_asset_live_compute, monkeypatch
):
    stub_providers(monkeypatch)
    backend = AlpacaBackend(fmp_api_key="test-key")
    backend.connect = lambda: True
    monkeypatch.setattr(backends, "create_backend", lambda *_: backend)
    monkeypatch.setattr(sys, "argv", ["emerald-exchange", "--transport", "stdio"])
    asyncio.run(_exercise(get_mcp_instance()[0]))


@pytest.mark.skipif(
    Version(version("epistemic-graph")) < Version("2.27.6"),
    reason="real connector pack replay requires graph 2.27.6",
)
def test_provider_records_through_sdk_and_graph(multi_asset_live_compute, monkeypatch):
    pytest.importorskip("agent_connector_sdk.finance.multi_asset_source")
    stub_providers(monkeypatch)
    backend = AlpacaBackend(fmp_api_key="test-key")
    backend.connect = lambda: True
    monkeypatch.setattr(backends, "create_backend", lambda *_: backend)
    monkeypatch.setattr(sys, "argv", ["emerald-exchange", "--transport", "stdio"])
    asyncio.run(_exercise(get_mcp_instance()[0], validate=True))
