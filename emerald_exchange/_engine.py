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
from typing import Any, NoReturn

logger = logging.getLogger(__name__)

ENGINE_REQUIRED_ERR = (
    "epistemic-graph engine unavailable. Set EPISTEMIC_GRAPH_ENDPOINT, "
    "EPISTEMIC_GRAPH_AUTH_SECRET_REF, EPISTEMIC_GRAPH_TENANT and "
    "EPISTEMIC_GRAPH_GRAPH and ensure the engine is running."
)

#: Namespace of the analysis -> algorithm -> served-method bindings in
#: ``ontology/quant.ttl``; epistemic-graph selects algorithms from it by SPARQL.
QUANT_VOCABULARY = "http://knuckles.team/kg/emerald-finance#"

# Sentinel so a cached None ("engine not reachable") is distinct from "unprobed".
_UNPROBED = object()
_COMPUTE_CACHE: Any = _UNPROBED


def finance_compute() -> Any:
    """Return the cached SDK compute adapter, or ``None`` if unreachable.

    Connects through :func:`scion_sdk.compute.connect_compute`
    (``EPISTEMIC_GRAPH_*`` settings, compute scopes only). A failed probe is
    cached so a dead endpoint is never re-probed per call.
    """
    global _COMPUTE_CACHE
    if _COMPUTE_CACHE is not _UNPROBED:
        return _COMPUTE_CACHE
    from scion_sdk.compute import ComputeUnavailableError, connect_compute

    try:
        _COMPUTE_CACHE = connect_compute()
        logger.info("epistemic-graph engine connected; Rust quant compute enabled")
    except ComputeUnavailableError as exc:
        logger.warning("Operation failed: error_type=%s", type(exc).__name__)
        _COMPUTE_CACHE = None
    return _COMPUTE_CACHE


def finance_engine() -> Any:
    """Return the connected epistemic-graph client, or ``None`` if unreachable."""
    compute = finance_compute()
    return None if compute is None else compute.client


def analysis_iri(name: str) -> str:
    """The IRI of one analysis declared in ``ontology/quant.ttl``."""
    return f"{QUANT_VOCABULARY}{name}"


#: Owner the missing served methods are handed off to.
HANDOFF_OWNER = "epistemic-graph EG-FINANCE"


def run_analysis(name: str, /, **params: Any) -> Any:
    """Run one ``quant.ttl`` analysis in epistemic-graph.

    The graph selects the algorithm by SPARQL over the analysis bindings and
    runs its served method through :mod:`scion_sdk.compute`.

    Raises:
        ComputeUnavailableError: the engine is not configured or unreachable.
        MethodNotServedError: no served algorithm is bound to the analysis.
    """
    from scion_sdk.compute import ComputeUnavailableError

    compute = finance_compute()
    if compute is None:
        raise ComputeUnavailableError(ENGINE_REQUIRED_ERR)
    return compute.analyse(analysis_iri(name), vocabulary=QUANT_VOCABULARY, **params)


def refuse(name: str) -> NoReturn:
    """Refuse an analysis epistemic-graph does not serve yet."""
    from scion_sdk.compute import MethodNotServedError

    raise MethodNotServedError(analysis_iri(name), handoff=HANDOFF_OWNER)


def engine_error(exc: BaseException) -> dict[str, Any]:
    """The tool payload for an unavailable engine or an unserved analysis."""
    from scion_sdk.compute import MethodNotServedError

    if isinstance(exc, MethodNotServedError):
        return {
            "error": "not_served",
            "method": exc.method,
            "handoff": exc.handoff or HANDOFF_OWNER,
        }
    return {"error": ENGINE_REQUIRED_ERR}


def reset_engine_cache() -> None:
    """Drop the cached client probe (primarily for tests)."""
    global _COMPUTE_CACHE
    _COMPUTE_CACHE = _UNPROBED
