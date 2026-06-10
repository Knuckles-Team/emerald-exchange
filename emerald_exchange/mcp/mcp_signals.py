"""Signal Generation MCP Tools — CONCEPT:EE-012."""

from typing import Any

import json
import logging

logger = logging.getLogger(__name__)


def _load_microstructure_priors() -> list[dict]:
    """Fetch stored MicrostructureSignal priors from the KG (CONCEPT:EE-033).

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
        logger.debug("microstructure prior load failed: %s", exc)
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
        """Signal generation and fusion. Routes to agent-utilities finance domain. CONCEPT:EE-012

        Actions:
        - 'regime': Detect current market regime
        - 'alpha': Generate alpha factors for a ticker
        - 'fuse': Bayesian signal fusion seeded from KG-stored signal priors.
          ``signals_json`` maps signal name -> direction (1 up / -1 down / 0).
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
                    return json.dumps({"error": f"invalid signals_json: {exc}"})

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

            return json.dumps({"error": f"Unknown action: {action}"})
        except ImportError as e:
            return json.dumps(
                {"error": f"agent-utilities finance module not available: {e}"}
            )
