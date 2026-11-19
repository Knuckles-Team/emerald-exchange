"""Signal Generation MCP Tools — CONCEPT:EX-AHE.harness.ee-11.

One typed tool per signal operation. Medulla selects and runs each algorithm.
"""

import json
import logging
from collections.abc import Callable
from itertools import pairwise
from typing import Annotated, Any

from pydantic import Field

from emerald_exchange.mcp._hints import READ
from emerald_exchange.signal_records import microstructure_signal_record

logger = logging.getLogger(__name__)


def _load_microstructure_priors() -> list[dict]:
    """Fetch stored MicrostructureSignal priors from the KG (CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion).

    Returns a list of property dicts (``directional_accuracy``,
    ``standalone_sharpe``, ``pbo``, ``name`` …) — empty when the engine is
    unreachable or holds no signals, so the fuse path degrades gracefully.
    """
    from .._engine import finance_engine

    engine = finance_engine()
    if engine is None:
        return []
    priors: list[dict] = []
    try:
        for node_id, node_type in engine.nodes.list():
            if str(node_type).split(".")[-1].lower() != "microstructure_signal":
                continue
            props = engine.nodes.properties(node_id) or {}
            if str(props.get("type", "")).split(".")[-1].lower() not in (
                "microstructure_signal",
                "",
            ):
                continue
            props.setdefault("name", node_id)
            priors.append(props)
    except Exception as exc:  # noqa: BLE001 — degrade to no priors
        logger.debug(
            "Microstructure prior load failed: error_type=%s", type(exc).__name__
        )
        return []
    return priors


def _number(record: dict, key: str, default: float) -> float:
    try:
        value = record.get(key, default)
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _fusion_priors(records: list[dict]) -> list[dict]:
    """Stored MicrostructureSignal records as medulla ``FusionPrior`` rows."""
    return [
        {
            "name": str(record.get("name") or record.get("id")),
            "directional_accuracy": _number(record, "directional_accuracy", 0.5),
            "standalone_sharpe": _number(record, "standalone_sharpe", 0.0),
            "pbo": _number(record, "pbo", 0.0),
        }
        for record in records
        if record.get("name") or record.get("id")
    ]


Ticker = Annotated[str, Field(description="Ticker the signal is about")]
Series = Annotated[list[float] | None, Field(description="Trailing window values")]


def _run(operation: str, compute: Callable[[], dict[str, Any]]) -> str:
    """Run one engine-backed signal; an unserved analysis says which method."""
    from scion_sdk.compute import MethodNotServedError

    try:
        return json.dumps(compute())
    except MethodNotServedError as exc:
        return json.dumps(
            {"error": "not_served", "operation": operation, "method": exc.method}
        )


def _floats(values: list[float] | None) -> list[float]:
    return [float(x) for x in values or []]


def register_signal_tools(mcp: Any) -> None:
    """Register the signal tools. CONCEPT:EX-AHE.harness.ee-11"""
    from .._engine import ENGINE_REQUIRED_ERR, analysis_iri, finance_compute
    from .._engine import QUANT_VOCABULARY as VOCAB

    @mcp.tool(tags={"signals"}, annotations=READ)
    def emerald_signals_regime(
        close_prices: Annotated[
            list[float], Field(description="Close prices, oldest first")
        ],
        ticker: Ticker = "",
    ) -> str:
        """Detect the current market regime (engine HMM over returns). CONCEPT:EX-AHE.harness.ee-11"""

        def compute() -> dict[str, Any]:
            prices = _floats(close_prices)
            if len(prices) < 3:
                return {
                    "ticker": ticker,
                    "operation": "regime",
                    "note": "Pass at least 3 close_prices",
                }
            engine = finance_compute()
            if engine is None:
                return {"error": ENGINE_REQUIRED_ERR}
            returns = [
                (current / previous) - 1.0
                for previous, current in pairwise(prices)
                if previous
            ]
            fitted = engine.analyse(
                analysis_iri("RegimeAnalysis"),
                vocabulary=VOCAB,
                observations=returns,
                n_states=2,
                max_iter=100,
                tol=1e-4,
            )
            return {"ticker": ticker, "operation": "regime", "regimes": fitted}

        return _run("regime", compute)

    @mcp.tool(tags={"signals"}, annotations=READ)
    def emerald_signals_alpha(ticker: Ticker) -> str:
        """Alpha factors for a ticker. CONCEPT:EX-AHE.harness.ee-11"""
        return json.dumps(
            {
                "ticker": ticker,
                "operation": "alpha",
                "note": "Route alpha_factors.py via finance workflow",
            }
        )

    @mcp.tool(tags={"signals"}, annotations=READ)
    def emerald_signals_fuse(
        directions: Annotated[
            dict[str, int],
            Field(description="Signal name to direction: 1 up, -1 down, 0 flat"),
        ],
        ticker: Ticker = "",
    ) -> str:
        """Bayesian signal fusion seeded from KG-stored signal priors. CONCEPT:EX-AHE.harness.ee-11"""

        def compute() -> dict[str, Any]:
            engine = finance_compute()
            if engine is None:
                return {"error": ENGINE_REQUIRED_ERR}
            fused = engine.analyse(
                analysis_iri("SignalFusionAnalysis"),
                vocabulary=VOCAB,
                request={
                    "prior": 0.5,
                    "priors": _fusion_priors(_load_microstructure_priors()),
                    "directions": {str(k): int(v) for k, v in directions.items()},
                },
            )
            return {
                "ticker": ticker,
                "operation": "fuse",
                "posterior_up": fused["posterior_up"],
                "seeded_from_kg": fused["seeded"],
                "sources": sorted(src["name"] for src in fused["sources"]),
            }

        return _run("fuse", compute)

    @mcp.tool(tags={"signals"}, annotations=READ)
    def emerald_signals_surveillance(
        ticker: Ticker = "",
        asset_class: Annotated[str, Field(description="Asset class")] = "equity",
        buy_vol: Series = None,
        sell_vol: Series = None,
        p_mean: Series = None,
        signed_flow: Series = None,
        price_changes: Series = None,
        baseline_sigma: Annotated[
            float, Field(description="Baseline price volatility")
        ] = 0.0,
    ) -> str:
        """Kyle insider/stealth-trading surveillance scores (CONCEPT:EX-AHE.harness.ee-31).

        Takes a trailing book/flow window. Returns informed-flow /
        detection-hazard / legal-risk scores and registers a discoverable
        MicrostructureSignal (priors set later by ``emerald_strategy_backtest``).
        DEFENSIVE: informed-flow detection, not trade concealment.
        """

        def compute() -> dict[str, Any]:
            engine = finance_compute()
            client = None if engine is None else engine.client
            if client is None:
                return {"error": ENGINE_REQUIRED_ERR}
            try:
                scores = engine.analyse(
                    analysis_iri("SurveillanceAnalysis"),
                    vocabulary=VOCAB,
                    buy_vol=_floats(buy_vol),
                    sell_vol=_floats(sell_vol),
                    p_mean=_floats(p_mean),
                    signed_flow=_floats(signed_flow),
                    price_changes=_floats(price_changes),
                    baseline_sigma=float(baseline_sigma),
                )
            except Exception as exc:  # noqa: BLE001 — degrade cleanly
                from scion_sdk.compute import MethodNotServedError

                if isinstance(exc, MethodNotServedError):
                    raise
                return {"error": "Operation failed"}

            # Register the detector as a discoverable MicrostructureSignal so the
            # fuse path finds it; priors (accuracy/sharpe/pbo) stay at defaults
            # until an ``emerald_strategy_backtest`` writes them (CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion).
            signal_id = f"kyle_surveillance:{ticker}" if ticker else "kyle_surveillance"
            registered = False
            try:
                record = microstructure_signal_record(
                    signal_id,
                    name="Kyle insider/stealth surveillance",
                    asset_class=asset_class,
                    decay_regime="regime_dependent",
                    provenance="paper:arxiv:2605.27684",
                )
                client.nodes.add(signal_id, record)
                registered = True
            except Exception as exc:  # noqa: BLE001 — scores still returned
                logger.debug("Operation failed: error_type=%s", type(exc).__name__)

            return {
                "ticker": ticker,
                "operation": "surveillance",
                "signal_id": signal_id,
                "registered": registered,
                **scores,
            }

        return _run("surveillance", compute)

    @mcp.tool(tags={"signals"}, annotations=READ)
    def emerald_signals_insider_equilibrium(
        ticker: Ticker = "",
        sigma_v: Annotated[float, Field(description="Asset value volatility")] = 0.30,
        sigma_u: Annotated[float, Field(description="Noise-trader volatility")] = 1.00,
        gap_var: Annotated[
            float | None, Field(description="Information gap variance")
        ] = None,
        enforcement: Annotated[
            float, Field(description="Enforcement intensity")
        ] = 0.50,
        surveillance_kappa: Annotated[
            float, Field(description="Surveillance sensitivity")
        ] = 1.0,
        criminal_penalty: Annotated[float, Field(description="Criminal penalty")] = 0.0,
        civil_penalty_rate: Annotated[
            float, Field(description="Civil penalty rate")
        ] = 0.0,
        horizon: Annotated[float, Field(description="Trading horizon")] = 1.0,
        steps: Annotated[int, Field(description="Schedule steps")] = 10,
    ) -> str:
        """Strategic insider equilibrium under DYNAMIC legal risk (CONCEPT:EX-AHE.harness.ee-32).

        Distils arXiv:2605.27684 (Qiao & Xia) and deepens the snapshot
        surveillance score into the full continuous-time game. Returns the
        equilibrium trading intensity, the end-of-window acceleration schedule,
        and a penalty-policy verdict (criminal vs civil levers). DEFENSIVE: a
        regulator/surveillance-design tool, not a trade-concealment aid.
        """

        def compute() -> dict[str, Any]:
            inputs = {
                "sigma_v": sigma_v,
                "sigma_u": sigma_u,
                "enforcement": enforcement,
                "surveillance_kappa": surveillance_kappa,
                "criminal_penalty": criminal_penalty,
                "civil_penalty_rate": civil_penalty_rate,
                "horizon": horizon,
            }
            if gap_var is not None:
                inputs["gap_var"] = gap_var
            engine = finance_compute()
            if engine is None:
                return {"error": ENGINE_REQUIRED_ERR}
            analysis = engine.analyse(
                analysis_iri("InsiderEquilibriumAnalysis"),
                vocabulary=VOCAB,
                request={"inputs": inputs, "steps": steps},
            )
            return {
                "ticker": ticker,
                "operation": "insider_equilibrium",
                "equilibrium": analysis["equilibrium"],
                "schedule": analysis["schedule"],
                "policy": analysis["policy"],
            }

        return _run("insider_equilibrium", compute)
