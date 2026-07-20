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
    socket_path = os.environ.get("EPISTEMIC_GRAPH_SOCKET") or os.environ.get(
        "GRAPH_SERVICE_SOCKET"
    )
    tcp_addr = os.environ.get("EPISTEMIC_GRAPH_TCP")
    try:
        from epistemic_graph.client import SyncEpistemicGraphClient

        if tcp_addr:
            client = SyncEpistemicGraphClient.connect(tcp_addr=tcp_addr)
        elif socket_path:
            client = SyncEpistemicGraphClient.connect(socket_path=socket_path)
        else:
            client = SyncEpistemicGraphClient.connect()
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
