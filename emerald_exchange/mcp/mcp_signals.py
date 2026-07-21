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


def register_signal_tools(mcp: Any) -> None:

    @mcp.tool(tags=["signals"])
    def emerald_signals(
        action: str,
        ticker: str = "",
        asset_class: str = "equity",
        signals_json: str = "{}",
    ) -> str:
        """Signal generation and fusion. Routes to agent-utilities finance domain. CONCEPT:EX-AHE.harness.ee-11

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
        try:
            if action == "regime":
                from agent_utilities.domains.finance.regime_detector import (
                    RegimeDetector,
                )

                _ = RegimeDetector()
                return json.dumps(
                    {
                        "ticker": ticker,
                        "action": "regime",
                        "note": "Use with historical DataFrame via data-science-mcp",
                    }
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
                from agent_utilities.domains.finance.signal_fusion import (
                    BayesianSignalFusion,
                )

                try:
                    directions = {
                        str(k): int(v) for k, v in json.loads(signals_json).items()
                    }
                except (ValueError, TypeError, AttributeError) as exc:
                    return json.dumps({"error": f"invalid signals_json: {type(exc).__name__}"})

                fusion = BayesianSignalFusion()
                priors = _load_microstructure_priors()
                seeded = fusion.seed_from_kg(priors)
                # Any directions without a KG prior get a neutral source so the
                # fuse still incorporates them (unseeded = default accuracy 0.6).
                for name in directions:
                    if name not in fusion.sources:
                        fusion.register_source(name, weight=0.5, accuracy=0.55)

                posterior = fusion.fuse(directions)
                return json.dumps(
                    {
                        "ticker": ticker,
                        "action": "fuse",
                        "posterior_up": posterior,
                        "seeded_from_kg": seeded,
                        "sources": sorted(fusion.sources),
                    }
                )

            elif action == "surveillance":
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
                    from agent_utilities.models.domains.finance import (
                        MicrostructureSignalNode,
                    )

                    node = MicrostructureSignalNode(
                        id=signal_id,
                        name="Kyle insider/stealth surveillance",
                        asset_class=asset_class,
                        decay_regime="regime_dependent",
                        provenance="paper:arxiv:2605.27684",
                    )
                    engine.nodes.add(signal_id, node.model_dump(mode="json"))
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
                from agent_utilities.domains.finance.insider_equilibrium import (
                    InsiderEquilibriumInputs,
                    intensity_schedule,
                    penalty_policy_analysis,
                    solve_equilibrium,
                )

                try:
                    params = json.loads(signals_json) if signals_json else {}
                except (ValueError, TypeError) as exc:
                    return json.dumps({"error": f"invalid signals_json: {type(exc).__name__}"})

                steps = int(params.pop("steps", 10))
                allowed = InsiderEquilibriumInputs.__dataclass_fields__
                try:
                    kwargs = {k: float(v) for k, v in params.items() if k in allowed}
                except (ValueError, TypeError) as exc:
                    return json.dumps({"error": f"invalid equilibrium params: {type(exc).__name__}"})

                inputs = InsiderEquilibriumInputs(**kwargs)
                eq = solve_equilibrium(inputs)
                schedule = intensity_schedule(inputs, steps=steps)
                policy = penalty_policy_analysis(inputs)
                return json.dumps(
                    {
                        "ticker": ticker,
                        "action": "insider_equilibrium",
                        "equilibrium": eq.to_dict(),
                        "schedule": schedule,
                        "policy": policy.to_dict(),
                    }
                )

            return json.dumps({"error": f"Unknown action: {action}"})
        except ImportError as e:
            return json.dumps(
                {"error": f"agent-utilities finance module not available: {type(e).__name__}"}
            )
