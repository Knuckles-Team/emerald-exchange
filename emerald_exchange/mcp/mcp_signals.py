"""Signal Generation MCP Tools — CONCEPT:EX-AHE.harness.ee-11."""

import json
import logging
from itertools import pairwise
from typing import Any

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


#: Insider-equilibrium inputs and their defaults (epistemic-graph ``InsiderInputs``).
_INSIDER_DEFAULTS: dict[str, float] = {
    "sigma_v": 0.30,
    "sigma_u": 1.00,
    "enforcement": 0.50,
    "surveillance_kappa": 1.0,
    "criminal_penalty": 0.0,
    "civil_penalty_rate": 0.0,
    "horizon": 1.0,
}


def _number(record: dict, key: str, default: float) -> float:
    try:
        value = record.get(key, default)
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _fusion_priors(records: list[dict]) -> list[dict]:
    """Stored MicrostructureSignal records as epistemic-graph ``FusionPrior`` rows."""
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


def register_signal_tools(mcp: Any) -> None:

    @mcp.tool(tags=["signals"])
    def emerald_signals(
        action: str,
        ticker: str = "",
        asset_class: str = "equity",
        signals_json: str = "{}",
    ) -> str:
        """Signal generation and fusion. Epistemic-graph selects and runs each algorithm. CONCEPT:EX-AHE.harness.ee-11

        Actions:
        - 'regime': Detect current market regime
        - 'alpha': Generate alpha factors for a ticker
        - 'fuse': Bayesian signal fusion seeded from KG-stored signal priors.
          ``signals_json`` maps signal name -> direction (1 up / -1 down / 0).
        - 'surveillance': Kyle insider/stealth-trading surveillance scores
          (CONCEPT:EX-AHE.harness.ee-31). ``signals_json`` is a trailing book/flow window
          ``{buy_vol, sell_vol, p_mean, signed_flow, price_changes,
          baseline_sigma}``. Returns informed-flow / detection-hazard /
          legal-risk scores and registers a discoverable MicrostructureSignal
          (priors set later by ``emerald_strategy`` backtest). DEFENSIVE:
          informed-flow detection, not trade concealment.
        - 'insider_equilibrium': Strategic insider equilibrium under DYNAMIC legal
          risk (CONCEPT:EX-AHE.harness.ee-32, distils arXiv:2605.27684 Qiao & Xia). Deepens the
          snapshot 'surveillance' score into the full continuous-time game:
          ``signals_json`` carries model primitives ``{sigma_v, sigma_u, gap_var,
          enforcement, surveillance_kappa, criminal_penalty, civil_penalty_rate,
          horizon, steps}``. Returns the equilibrium trading intensity β*, the
          end-of-window acceleration schedule, and a penalty-policy verdict
          (criminal vs civil levers). DEFENSIVE: a regulator/surveillance-design
          tool, not a trade-concealment aid — it quantifies which enforcement
          levers constrain an insider.
        """
        from agent_connector_sdk.compute import MethodNotServedError

        from .._engine import ENGINE_REQUIRED_ERR, analysis_iri, finance_compute
        from .._engine import QUANT_VOCABULARY as VOCAB

        try:
            if action == "regime":
                try:
                    payload = json.loads(signals_json) if signals_json else {}
                    prices = [float(x) for x in payload.get("close_prices", [])]
                except (ValueError, TypeError, AttributeError) as exc:
                    return json.dumps(
                        {"error": f"invalid signals_json: {type(exc).__name__}"}
                    )
                if len(prices) < 3:
                    return json.dumps(
                        {
                            "ticker": ticker,
                            "action": "regime",
                            "note": "Pass close_prices in signals_json",
                        }
                    )
                compute = finance_compute()
                if compute is None:
                    return json.dumps({"error": ENGINE_REQUIRED_ERR})
                returns = [
                    (current / previous) - 1.0
                    for previous, current in pairwise(prices)
                    if previous
                ]
                fitted = compute.analyse(
                    analysis_iri("RegimeAnalysis"),
                    vocabulary=VOCAB,
                    observations=returns,
                    n_states=2,
                    max_iter=100,
                    tol=1e-4,
                )
                return json.dumps(
                    {"ticker": ticker, "action": "regime", "regimes": fitted}
                )

            elif action == "alpha":
                return json.dumps(
                    {
                        "ticker": ticker,
                        "action": "alpha",
                        "note": "Route alpha_factors.py via finance workflow",
                    }
                )

            elif action == "fuse":
                try:
                    directions = {
                        str(k): int(v) for k, v in json.loads(signals_json).items()
                    }
                except (ValueError, TypeError, AttributeError) as exc:
                    return json.dumps(
                        {"error": f"invalid signals_json: {type(exc).__name__}"}
                    )

                compute = finance_compute()
                if compute is None:
                    return json.dumps({"error": ENGINE_REQUIRED_ERR})
                fused = compute.analyse(
                    analysis_iri("SignalFusionAnalysis"),
                    vocabulary=VOCAB,
                    request={
                        "prior": 0.5,
                        "priors": _fusion_priors(_load_microstructure_priors()),
                        "directions": directions,
                    },
                )
                return json.dumps(
                    {
                        "ticker": ticker,
                        "action": "fuse",
                        "posterior_up": fused["posterior_up"],
                        "seeded_from_kg": fused["seeded"],
                        "sources": sorted(src["name"] for src in fused["sources"]),
                    }
                )

            elif action == "surveillance":
                compute = finance_compute()
                engine = None if compute is None else compute.client
                if engine is None:
                    return json.dumps({"error": ENGINE_REQUIRED_ERR})
                try:
                    book = json.loads(signals_json)
                except (ValueError, TypeError) as exc:
                    return json.dumps(
                        {"error": f"invalid signals_json: {type(exc).__name__}"}
                    )

                try:
                    scores = compute.analyse(
                        analysis_iri("SurveillanceAnalysis"),
                        vocabulary=VOCAB,
                        buy_vol=[float(x) for x in book.get("buy_vol", [])],
                        sell_vol=[float(x) for x in book.get("sell_vol", [])],
                        p_mean=[float(x) for x in book.get("p_mean", [])],
                        signed_flow=[float(x) for x in book.get("signed_flow", [])],
                        price_changes=[float(x) for x in book.get("price_changes", [])],
                        baseline_sigma=float(book.get("baseline_sigma", 0.0)),
                    )
                except MethodNotServedError:
                    raise
                except Exception:  # noqa: BLE001 — degrade cleanly
                    return json.dumps({"error": "Operation failed"})

                # Register the detector as a discoverable MicrostructureSignal so the
                # fuse path finds it; priors (accuracy/sharpe/pbo) stay at defaults
                # until an ``emerald_strategy`` backtest writes them (CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion).
                signal_id = (
                    f"kyle_surveillance:{ticker}" if ticker else "kyle_surveillance"
                )
                registered = False
                try:
                    record = microstructure_signal_record(
                        signal_id,
                        name="Kyle insider/stealth surveillance",
                        asset_class=asset_class,
                        decay_regime="regime_dependent",
                        provenance="paper:arxiv:2605.27684",
                    )
                    engine.nodes.add(signal_id, record)
                    registered = True
                except Exception as exc:  # noqa: BLE001 — scores still returned
                    logger.debug("Operation failed: error_type=%s", type(exc).__name__)

                return json.dumps(
                    {
                        "ticker": ticker,
                        "action": "surveillance",
                        "signal_id": signal_id,
                        "registered": registered,
                        **scores,
                    }
                )

            elif action == "insider_equilibrium":
                try:
                    params = json.loads(signals_json) if signals_json else {}
                except (ValueError, TypeError) as exc:
                    return json.dumps(
                        {"error": f"invalid signals_json: {type(exc).__name__}"}
                    )

                try:
                    steps = int(params.pop("steps", 10))
                    inputs = {**_INSIDER_DEFAULTS}
                    inputs.update(
                        {
                            k: float(v)
                            for k, v in params.items()
                            if k in _INSIDER_DEFAULTS
                        }
                    )
                    if params.get("gap_var") is not None:
                        inputs["gap_var"] = float(params["gap_var"])
                except (ValueError, TypeError) as exc:
                    return json.dumps(
                        {"error": f"invalid equilibrium params: {type(exc).__name__}"}
                    )

                compute = finance_compute()
                if compute is None:
                    return json.dumps({"error": ENGINE_REQUIRED_ERR})
                analysis = compute.analyse(
                    analysis_iri("InsiderEquilibriumAnalysis"),
                    vocabulary=VOCAB,
                    request={"inputs": inputs, "steps": steps},
                )
                return json.dumps(
                    {
                        "ticker": ticker,
                        "action": "insider_equilibrium",
                        "equilibrium": analysis["equilibrium"],
                        "schedule": analysis["schedule"],
                        "policy": analysis["policy"],
                    }
                )

            return json.dumps({"error": f"Unknown action: {action}"})
        except MethodNotServedError as exc:
            return json.dumps(
                {"error": "not_served", "action": action, "method": exc.method}
            )
