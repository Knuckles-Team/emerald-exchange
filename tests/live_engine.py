"""A real, ephemeral epistemic-graph server for live-engine tests.

Starts the ``epistemic-graph-server`` binary from ``medulla[server]``
on a private Unix socket with test-only credentials, enrolls the test signer,
creates one graph, imports emerald's ``ontology/quant.ttl`` into it, and
installs a connected :class:`~agent_connector_sdk.compute.EngineCompute` as
emerald's engine. Analyses are then selected by SPARQL and run by the real
engine. Tests skip only when the server package is not installed.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - fixed server argv, test-only
import time
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path

import pytest
from agent_connector_sdk.compute import EngineCompute, connect_compute
from agent_connector_sdk.ingest.engine import EngineSettings

from emerald_exchange import _engine

AUDIENCE = "epistemic-graph"
TENANT = "tenant:emerald-test"
POLICY = "policy:current"
PRINCIPAL = "service:connector"
GRAPH = "emerald-live"
_HMAC_KEY = "emerald-live-engine-" + "test-secret-0123456789abcdef"  # nosec B105
_SIGNER_KEY = "emerald-live-engine-" + "signer-key-0123456789abcdef"  # nosec B105
_DATA_KEY = "emerald-live-engine-" + "encryption-key-0123456789abcdef"  # nosec B105
_HMAC_ENV = "EMERALD_LIVE_ENGINE_SECRET"
_LIVE_SOCKET: dict[str, Path] = {}


def _context(roles: list[str], scopes: list[str]) -> dict[str, object]:
    return {
        "principal": PRINCIPAL,
        "tenant": TENANT,
        "audience": AUDIENCE,
        "agent_id": PRINCIPAL,
        "roles": roles,
        "scopes": scopes,
        "policy_version": POLICY,
        "delegation": [],
    }


def _wait_for(socket_path: Path, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("epistemic-graph-server exited during startup")
        if socket_path.exists():
            return
        time.sleep(0.05)
    raise RuntimeError("epistemic-graph-server did not open its socket")


_OPEN_POLICY = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:emerald-exchange:test-policy#> .
ex:OpenPolicy a sh:NodeShape ;
    sh:targetClass ex:NeverInstantiated .
"""


def _bootstrap(socket_path: Path) -> None:
    from epistemic_graph.client import SyncEpistemicGraphClient

    client = SyncEpistemicGraphClient.connect(
        socket_path=str(socket_path),
        auth_secret=_HMAC_KEY,
        verified_context=_context([], ["security:bootstrap"]),
    )
    try:
        client.consensus.bootstrap_system_identity(
            agent_id=PRINCIPAL, signer_id=PRINCIPAL, signer_key=_SIGNER_KEY
        )
    finally:
        client.close()
    client = SyncEpistemicGraphClient.connect(
        socket_path=str(socket_path),
        auth_secret=_HMAC_KEY,
        verified_context=_context(["test"], ["*"]),
    )
    try:
        client.tenants.create(GRAPH)
    finally:
        client.close()
    client = SyncEpistemicGraphClient.connect(
        socket_path=str(socket_path),
        auth_secret=_HMAC_KEY,
        graph_name=GRAPH,
        verified_context=_context(["test"], ["*"]),
    )
    try:
        ttl = files("emerald_exchange.ontology").joinpath("quant.ttl").read_text()
        # The engine requires a registered integrity policy before it accepts
        # any RDF write; a shape targeting a class nothing instantiates registers
        # one without constraining the ontology load.
        client.rdf.icv_configure(_OPEN_POLICY)
        client.rdf.add_triples(turtle=ttl)
    finally:
        client.close()


@pytest.fixture(scope="session")
def live_compute(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[EngineCompute]:
    """emerald's engine, connected to a fresh real epistemic-graph server."""
    from epistemic_graph.server_binary import (
        ServerBinaryNotFoundError,
        resolve_server_binary,
    )

    try:
        binary = resolve_server_binary()
    except ServerBinaryNotFoundError:
        pytest.skip("medulla[server] is not installed")
    root = Path(tmp_path_factory.mktemp("eg"))
    socket_path = root / "eg.sock"
    _LIVE_SOCKET["path"] = socket_path
    (root / "security").mkdir()
    env = {
        **os.environ,
        "GRAPH_SERVICE_AUTH_SECRET": _HMAC_KEY,
        "EPISTEMIC_GRAPH_AUDIENCE": AUDIENCE,
        "EPISTEMIC_GRAPH_TENANT": TENANT,
        "EPISTEMIC_GRAPH_POLICY_VERSION": POLICY,
        "EPISTEMIC_GRAPH_REQUIRE_OIDC": "false",
        "EPISTEMIC_GRAPH_SECURITY_STATE_DIR": str(root / "security"),
        "EPISTEMIC_GRAPH_SIGNER_KEYS_JSON": json.dumps(
            {
                PRINCIPAL: {
                    "key": _SIGNER_KEY,
                    "allowed_roles": [],
                    "may_grant_system": True,
                }
            }
        ),
        "EPISTEMIC_GRAPH_ENCRYPTION_KEY": _DATA_KEY,
    }
    with (root / "engine.log").open("wb") as log:
        proc = subprocess.Popen(  # nosec B603 - fixed argv
            [
                binary,
                "--socket-path",
                str(socket_path),
                "--auth-secret",
                _HMAC_KEY,
                "--persist-dir",
                str(root / "data"),
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for(socket_path, proc)
            _bootstrap(socket_path)
            os.environ[_HMAC_ENV] = _HMAC_KEY
            compute = connect_compute(
                EngineSettings(
                    endpoint=f"unix://{socket_path}",
                    auth_secret_ref=f"env://{_HMAC_ENV}",
                    tenant=TENANT,
                    graph=GRAPH,
                    principal=PRINCIPAL,
                    policy_version=POLICY,
                )
            )
            yield compute
        finally:
            compute = None
            proc.terminate()
            proc.wait(timeout=30)
            _LIVE_SOCKET.clear()


@pytest.fixture
def live_engine(
    live_compute: EngineCompute, monkeypatch: pytest.MonkeyPatch
) -> EngineCompute:
    """Install the live engine as emerald's compute for one test."""
    monkeypatch.setattr(_engine, "_COMPUTE_CACHE", live_compute)
    return live_compute


def served_mcp():
    """The in-process connector server without its per-caller request throttle.

    The throttle guards a public endpoint; these tests replay the whole pack
    from one anonymous in-process caller in a burst, so it would only make the
    result depend on scheduling. Everything else in the middleware stack stays.
    """
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

    from emerald_exchange.mcp_server import get_mcp_instance

    mcp = get_mcp_instance()[0]
    mcp.middleware[:] = [
        m for m in mcp.middleware if not isinstance(m, RateLimitingMiddleware)
    ]
    return mcp
