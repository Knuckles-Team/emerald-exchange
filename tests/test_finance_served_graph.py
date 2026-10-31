"""Real owner connector pack and graph replay with a synthetic provider."""

import asyncio
import hashlib
import json
import sys
from importlib.metadata import version
from types import SimpleNamespace

import pytest
from epistemic_graph import EpistemicGraphClient
from epistemic_graph.connector_pack import ConnectorPackClient
from epistemic_graph.generated.connector_pack import (
    AgentLibraryMutationContext,
    McpCatalogSnapshotBinding,
    PackProducer,
)
from packaging.version import Version
from scion_sdk.adapters.mcp_tool import McpToolSourceAdapter
from scion_sdk.artifacts.pack import build_content_pack
from scion_sdk.artifacts.resources import ResourceArtifactKind
from scion_sdk.artifacts.tools import ToolArtifactKind
from scion_sdk.ingest.live_declaration import load_declaration as declaration
from scion_sdk.manifest.presets import ToolPreset
from scion_sdk.ports.session import TransportEndpoint
from scion_sdk.runner.syncing import SyncTarget, sync_stream
from scion_sdk.sinks.epistemic_graph import EpistemicGraphSink
from scion_sdk.transports.mcp import McpTransport

from emerald_exchange.backends import AlpacaBackend
from tests.live_engine import (
    _HMAC_KEY,
    _LIVE_SOCKET,
    PRINCIPAL,
    TENANT,
    _context,
)
from tests.live_engine import live_compute as _live_compute


def _catalog():
    return McpCatalogSnapshotBinding(
        configuration_revision=7,
        catalog_generation=11,
        snapshot_digest="a" * 64,
        child_connection_generation=3,
        authorization_scope_digest="b" * 64,
    )


def _mutation_context():
    return AgentLibraryMutationContext(
        request_id=1,
        principal="principal-a",
        caller_principal="caller-a",
        attempt_nonce="07" * 32,
        tenant_id=TENANT,
        actor_scope="scope-a",
        purpose_id="purpose-a",
        policy_revision="policy-1",
        policy_digest="sha256:" + "c" * 64,
        policy_decision_id="decision-1",
        idempotency_key="caller-value",
        expected_revision=1,
        trace_id="trace-1",
        created_at_ms=1700000000000,
    )


async def scoped_client(scopes):
    return await EpistemicGraphClient.connect(
        socket_path=str(_LIVE_SOCKET["path"]),
        auth_secret=_HMAC_KEY,
        graph_name="emerald-live",
        verified_context=_context(["connector"], scopes),
    )


CONNECTOR = "emerald-exchange-mcp"
CSV = "date,side,qty,price,fee,ccy,settle\n2026-01-02T00:00:00Z,buy,10,100.5,1,USD,2026-01-04T00:00:00Z\n"
MAPPING = {
    "date": "event_time_utc",
    "side": "action",
    "qty": "quantity",
    "price": "price",
    "fee": "fees",
    "ccy": "currency",
    "settle": "settlement_time_utc",
}


class Provider:
    def get_account(self):
        return SimpleNamespace(
            id="account-1", currency="USD", equity="10", cash="9", buying_power="8"
        )

    def get_all_positions(self):
        return [
            SimpleNamespace(
                symbol="ABC",
                qty="1",
                avg_entry_price="2",
                current_price="3",
                unrealized_pl="1",
            )
        ]


async def exercise(mcp, *, validate=False):
    client = await scoped_client(["*"])
    try:
        context = _mutation_context().model_copy(update={"tenant_id": TENANT})
        key = "owner-pack-finance:bind"
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
        async with McpTransport().session(TransportEndpoint(in_process=mcp)) as session:
            assert "connector://resources" in {
                str(r.uri) for r in await session.list_resources()
            }
            raw = await session.read_resource("connector://resources")
            served = json.loads(raw)
            assert {s["source_id"] for s in served["sources"]} >= {
                "alpaca-account",
                "alpaca-account-positions",
                "alpaca-csv-activities",
            }
            assert "Activity" in served["schema_mappings"]
            pack = await build_content_pack(
                session,
                connector=CONNECTOR,
                kinds=[ToolArtifactKind(), ResourceArtifactKind()],
            )
            imported = await ConnectorPackClient(client).import_pack(
                pack.archive,
                connector=CONNECTOR,
                server_package_version=pack.server_package_version,
                producer=PackProducer(name="owner-pack-test", version="1"),
                catalog=_catalog(),
                context=context,
            )
            assert imported.result == "imported"

            async def authority(_):
                return _catalog(), context

            target = SyncTarget(
                CONNECTOR, EpistemicGraphSink(client, authority), max_pages=1
            )
            adapters = []
            for source_id, kind in [
                ("alpaca-account", "Account"),
                ("alpaca-account-positions", "Position"),
                ("alpaca-csv-activities", "Activity"),
            ]:
                source = next(
                    s
                    for s in declaration("emerald_exchange").sources
                    if s.source_id == source_id
                )
                raw = dict(source.preset)
                raw.update(
                    {
                        "server": CONNECTOR,
                        "tool": source.tools[0],
                        "id_field": source.id_field,
                        "text_field": source.text_field,
                        "title_field": source.title_field,
                        "records_path": source.records_path,
                    }
                )
                if kind == "Activity":
                    raw["params"] = {
                        **raw["params"],
                        "content": CSV,
                        "mapping": MAPPING,
                        "tenant_id": TENANT,
                        "instrument_id": "ABC",
                        "license_tag": "licensed",
                    }
                preset = ToolPreset.from_mapping(source_id, raw)
                adapter = McpToolSourceAdapter(
                    preset,
                    connector=CONNECTOR,
                    mapping_reference=f"connector:{CONNECTOR}#mappings/{kind}",
                )
                if validate:
                    from scion_sdk.finance.account_source import (
                        AccountSourceAdapter,
                        AccountSourceKind,
                    )

                    adapter = AccountSourceAdapter(
                        adapter,
                        account_kind=AccountSourceKind(kind.lower()),
                        tenant_id=TENANT,
                        account_id="account-1",
                    )
                adapters.append(adapter)
            for _ in range(2):
                for adapter in adapters:
                    assert (await sync_stream(session, adapter, target)).accepted == 1
        rows = await client.query.cypher_read(
            "MATCH (n) WHERE n.source_stream IS NOT NULL RETURN n LIMIT 100"
        )
        nodes = [
            r["n"]
            for r in rows
            if r["n"].get("source_stream")
            in {"alpaca-account", "alpaca-account-positions", "alpaca-csv-activities"}
        ]
        assert len(nodes) == 3
        (account,) = (n for n in nodes if n["source_stream"] == "alpaca-account")
        (position,) = (
            n for n in nodes if n["source_stream"] == "alpaca-account-positions"
        )
        (activity,) = (
            n for n in nodes if n["source_stream"] == "alpaca-csv-activities"
        )
        assert account["source_record_id"] == "account-1"
        assert (position["account_id"], position["symbol"], position["qty"]) == (
            "account-1",
            "ABC",
            1,
        )
        assert (activity["account_id"], activity["quantity"]) == ("account-1", 10)
    finally:
        await client.close()


@pytest.mark.skipif(
    Version(version("medulla")) < Version("2.27.6"),
    reason="real connector pack replay requires graph 2.27.6",
)
def test_real_served_pack_reimports_account_positions_and_csv(
    account_original_engine, monkeypatch
):
    from emerald_exchange import backends
    from tests.live_engine import served_mcp

    backend = AlpacaBackend()
    backend._client = Provider()
    backend.connect = lambda: True
    monkeypatch.setattr(backends, "create_backend", lambda *args: backend)
    monkeypatch.setattr(sys, "argv", ["emerald-exchange", "--transport", "stdio"])
    mcp = served_mcp()
    asyncio.run(exercise(mcp))


@pytest.fixture(scope="session")
def account_original_engine(tmp_path_factory):
    yield from _live_compute.__wrapped__(tmp_path_factory)


@pytest.fixture
def account_adapter_engine(tmp_path_factory):
    yield from _live_compute.__wrapped__(tmp_path_factory)


@pytest.mark.skipif(
    Version(version("medulla")) < Version("2.27.6"),
    reason="real connector pack replay requires graph 2.27.6",
)
def test_account_validator_replays_all_sources(account_adapter_engine, monkeypatch):
    pytest.importorskip("scion_sdk.finance.account_source")
    from emerald_exchange import backends
    from tests.live_engine import served_mcp

    backend = AlpacaBackend()
    backend._client = Provider()
    backend.connect = lambda: True
    monkeypatch.setattr(backends, "create_backend", lambda *args: backend)
    monkeypatch.setattr(sys, "argv", ["emerald-exchange", "--transport", "stdio"])
    asyncio.run(exercise(served_mcp(), validate=True))
