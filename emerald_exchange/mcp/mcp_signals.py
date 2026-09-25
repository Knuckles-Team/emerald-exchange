"""Signal Generation MCP Tools — CONCEPT:EX-AHE.harness.ee-11."""

from typing import Any

import json
import logging

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


#: Directions a fuse call accepts for a source without a measured prior.
_UNSEEDED_WEIGHT = 0.5
_UNSEEDED_ACCURACY = 0.55
_INSIDER_FIELDS = (
    "sigma_v",
    "sigma_u",
    "gap_var",
    "enforcement",
    "surveillance_kappa",
    "criminal_penalty",
    "civil_penalty_rate",
    "horizon",
)
#: The model's defaults: a moderately-enforced market, a real edge.
_INSIDER_DEFAULTS = {
    "sigma_v": 0.30,
    "sigma_u": 1.00,
    "enforcement": 0.50,
    "surveillance_kappa": 1.0,
    "criminal_penalty": 0.0,
    "civil_penalty_rate": 0.0,
    "horizon": 1.0,
}
_VERDICT_TEXT = {
    "enforcement_gated": (
        "Enforcement is weak: civil/financial penalties have vanishing effect. "
        "Raising fines cannot substitute for surveillance effort; only a "
        "criminal cost (or more enforcement) constrains the insider."
    ),
    "criminal_suppresses": (
        "The criminal penalty exceeds the suppression floor: equilibrium "
        "intensity is driven to zero, the binding hard constraint."
    ),
    "criminal_is_the_lever": (
        "The criminal cost can drive intensity to zero while civil damages only "
        "dampen it: criminal sanctions are the effective lever."
    ),
}


def microstructure_signal(signal_id: str, **fields: object) -> dict:
    """A ``microstructure_signal`` KG node body (the fuse path reads these)."""
    return {"id": signal_id, "type": "microstructure_signal", **fields}


def _prior(record: dict) -> dict | None:
    name = str(record.get("name") or record.get("id") or "")
    if not name:
        return None
    try:
        return {
            "name": name,
            "directional_accuracy": float(record.get("directional_accuracy", 0.5)),
            "standalone_sharpe": float(record.get("standalone_sharpe", 0.0)),
            "pbo": float(record.get("pbo", 0.0)),
        }
    except (TypeError, ValueError):
        return None


def _fuse(ticker: str, signals_json: str) -> str:
    from .._engine import ENGINE_REQUIRED_ERR, finance_engine

    try:
        directions = {str(k): int(v) for k, v in json.loads(signals_json).items()}
    except (ValueError, TypeError, AttributeError) as exc:
        return json.dumps({"error": f"invalid signals_json: {type(exc).__name__}"})
    engine = finance_engine()
    if engine is None:
        return json.dumps({"error": ENGINE_REQUIRED_ERR})
    priors = [p for p in map(_prior, _load_microstructure_priors()) if p is not None]
    fused = engine.finance.signal_models(
        "bayes_fuse",
        request={
            "priors": priors,
            "directions": directions,
            "default_weight": _UNSEEDED_WEIGHT,
            "default_accuracy": _UNSEEDED_ACCURACY,
        },
    )
    return json.dumps(
        {
            "ticker": ticker,
            "action": "fuse",
            "posterior_up": fused["posterior_up"],
            "seeded_from_kg": fused["seeded"],
            "sources": sorted(source["name"] for source in fused["sources"]),
        }
    )


def _insider_inputs(params: dict) -> dict:
    inputs = dict(_INSIDER_DEFAULTS)
    inputs.update(
        {k: float(v) for k, v in params.items() if k in _INSIDER_FIELDS}
    )
    return inputs


def _insider_equilibrium(ticker: str, signals_json: str) -> str:
    from .._engine import ENGINE_REQUIRED_ERR, finance_engine

    try:
        params = json.loads(signals_json) if signals_json else {}
        steps = int(params.pop("steps", 10))
        inputs = _insider_inputs(params)
    except (ValueError, TypeError, AttributeError) as exc:
        return json.dumps({"error": f"invalid equilibrium params: {type(exc).__name__}"})
    engine = finance_engine()
    if engine is None:
        return json.dumps({"error": ENGINE_REQUIRED_ERR})
    analysis = engine.finance.signal_models(
        "insider_equilibrium", request={"inputs": inputs, "steps": steps}
    )
    policy = dict(analysis["policy"])
    policy["verdict_text"] = _VERDICT_TEXT.get(str(policy.get("verdict")), "")
    return json.dumps(
        {
            "ticker": ticker,
            "action": "insider_equilibrium",
            "equilibrium": analysis["equilibrium"],
            "schedule": analysis["schedule"],
            "policy": policy,
        }
    )



def register_signal_tools(mcp: Any) -> None:

    @mcp.tool(tags=["signals"])
    def emerald_signals(
        action: str,
        ticker: str = "",
        asset_class: str = "equity",
        signals_json: str = "{}",
    ) -> str:
        """Signal fusion and surveillance models, computed by epistemic-graph. CONCEPT:EX-AHE.harness.ee-11

        Actions:
        - 'fuse': Bayesian signal fusion seeded from KG-stored signal priors
          (EG ``FinanceSignalModels.bayes_fuse``). ``signals_json`` maps signal
          name -> direction (1 up / -1 down / 0).
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
          levers constrain an insider. Computed by EG
          ``FinanceSignalModels.insider_equilibrium``.
        """
        try:
            if action == "fuse":
                return _fuse(ticker, signals_json)

            if action == "surveillance":
                from .._engine import ENGINE_REQUIRED_ERR, finance_engine

                engine = finance_engine()
                if engine is None:
                    return json.dumps({"error": ENGINE_REQUIRED_ERR})
                try:
                    book = json.loads(signals_json)
                except (ValueError, TypeError) as exc:
                    return json.dumps({"error": f"invalid signals_json: {type(exc).__name__}"})

                try:
                    scores = engine.finance.surveillance_risk(
                        buy_vol=[float(x) for x in book.get("buy_vol", [])],
                        sell_vol=[float(x) for x in book.get("sell_vol", [])],
                        p_mean=[float(x) for x in book.get("p_mean", [])],
                        signed_flow=[float(x) for x in book.get("signed_flow", [])],
                        price_changes=[float(x) for x in book.get("price_changes", [])],
                        baseline_sigma=float(book.get("baseline_sigma", 0.0)),
                    )
                except Exception:  # noqa: BLE001 — degrade cleanly
                    return json.dumps({"error": "Operation failed"})

                # Register the detector as a discoverable MicrostructureSignal so the
                # fuse path finds it; priors (accuracy/sharpe/pbo) stay at defaults
                # until an ``emerald_strategy`` backtest writes them (CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion).
                signal_id = f"kyle_surveillance:{ticker}" if ticker else "kyle_surveillance"
                registered = False
                try:
                    engine.nodes.add(
                        signal_id,
                        microstructure_signal(
                            signal_id,
                            name="Kyle insider/stealth surveillance",
                            asset_class=asset_class,
                            decay_regime="regime_dependent",
                            provenance="paper:arxiv:2605.27684",
                        ),
                    )
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
                return _insider_equilibrium(ticker, signals_json)

            return json.dumps({"error": f"Unknown action: {action}"})
        except ImportError as e:
            return json.dumps(
                {"error": f"finance engine client not available: {type(e).__name__}"}
            )
