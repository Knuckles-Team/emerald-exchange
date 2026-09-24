"""Lazy epistemic-graph engine client — CONCEPT:EX-AHE.harness.ee-20.

The heavy quant math (market-making quotes, VPIN, Bayesian Kelly, backtest
validation, forensic accounting) lives in the Rust ``epistemic-graph`` engine and
is reached over its MessagePack/UDS client (``epistemic_graph.client``,
``client.finance.*``). This module is the single, lazy integration point for
emerald-exchange so that *importing* any controller/utility never requires a
running engine.

The client is probed once and cached. A failed probe is cached too (distinct from
"unprobed" via a sentinel), so a dead endpoint is never re-probed per call.
Callers must treat ``None`` as "engine unreachable" and degrade gracefully.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

ENGINE_REQUIRED_ERR = (
    "epistemic-graph engine unavailable. Set EPISTEMIC_GRAPH_SOCKET or "
    "EPISTEMIC_GRAPH_TCP and ensure the engine is running."
)

# Sentinel so a cached None ("engine not reachable") is distinct from "unprobed".
_UNPROBED = object()
_CLIENT_CACHE: Any = _UNPROBED


def engine_endpoint() -> dict[str, str]:
    """The configured engine endpoint as client ``connect`` keyword arguments.

    ``EPISTEMIC_GRAPH_TCP`` (host:port) wins over ``EPISTEMIC_GRAPH_SOCKET`` /
    ``GRAPH_SERVICE_SOCKET`` (UDS); neither means the client's own default.
    """
    tcp_addr = os.environ.get("EPISTEMIC_GRAPH_TCP")
    if tcp_addr:
        return {"tcp_addr": tcp_addr}
    socket_path = os.environ.get("EPISTEMIC_GRAPH_SOCKET") or os.environ.get(
        "GRAPH_SERVICE_SOCKET"
    )
    return {"socket_path": socket_path} if socket_path else {}


#: Exactly what the live-order executor needs: read the approval lease, read
#: the durable change set and append its receipts (EH-423). Nothing else.
LIVE_ORDER_SCOPES = ("connector:write-back", "connector:write-back-read", "lease:read")


class EngineIdentityMissing(RuntimeError):
    """A workload-identity setting the verified engine context needs is unset."""


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EngineIdentityMissing(f"{name} is not set")
    return value


def live_order_context() -> dict[str, Any]:
    """The engine v2 verified context of emerald's live-order identity.

    Built from workload-identity-projected settings, like graph-os's own
    service contexts: ``EMERALD_EG_PRINCIPAL``, ``EPISTEMIC_GRAPH_TENANT``,
    ``AUTH_JWT_AUDIENCE`` and ``KG_POLICY_VERSION``. Fails closed when any is
    unset -- there is no default identity.
    """
    principal = _required_env("EMERALD_EG_PRINCIPAL")
    return {
        "principal": principal,
        "agent_id": principal,
        "tenant": _required_env("EPISTEMIC_GRAPH_TENANT"),
        "audience": _required_env("AUTH_JWT_AUDIENCE"),
        "roles": ["connector"],
        "scopes": list(LIVE_ORDER_SCOPES),
        "delegation": [],
        "policy_version": _required_env("KG_POLICY_VERSION"),
    }


def _principal_ref(principal: str) -> str:
    if principal.startswith("principal:sha256:"):
        return principal
    return "principal:sha256:" + hashlib.sha256(principal.encode()).hexdigest()


def live_order_approvers() -> frozenset[str]:
    """The people whose approval can authorise a live order (EH-423).

    ``EMERALD_LIVE_ORDER_APPROVERS`` is a comma-separated list of verified
    principals (or their EG persistence ids, ``principal:sha256:<hex>``). Unset
    or empty authorises nothing -- every live order is refused.
    """
    raw = os.environ.get("EMERALD_LIVE_ORDER_APPROVERS", "")
    return frozenset(_principal_ref(p.strip()) for p in raw.split(",") if p.strip())


def live_order_auth_secret() -> str:
    """The engine service secret the live-order client authenticates with."""
    return _required_env("GRAPH_SERVICE_AUTH_SECRET")


def finance_engine() -> Any:
    """Return a cached ``SyncEpistemicGraphClient``, or ``None`` if unreachable.

    Connects when an endpoint is configured via ``EPISTEMIC_GRAPH_SOCKET`` /
    ``GRAPH_SERVICE_SOCKET`` (UDS) or ``EPISTEMIC_GRAPH_TCP`` (host:port), and
    otherwise tries the client's own default socket. The result (including a
    failed probe) is cached so we never re-probe a dead endpoint per call.
    """
    global _CLIENT_CACHE
    if _CLIENT_CACHE is not _UNPROBED:
        return _CLIENT_CACHE

    client = None
    try:
        from epistemic_graph.client import SyncEpistemicGraphClient

        client = SyncEpistemicGraphClient.connect(**engine_endpoint())
        logger.info("epistemic-graph engine connected; Rust quant compute enabled")
    except Exception as exc:  # noqa: BLE001 — degrade gracefully when unreachable
        logger.warning("Operation failed: error_type=%s", type(exc).__name__)
        client = None
    _CLIENT_CACHE = client
    return client


def reset_engine_cache() -> None:
    """Drop the cached client probe (primarily for tests)."""
    global _CLIENT_CACHE
    _CLIENT_CACHE = _UNPROBED
