"""MicrostructureSignal records written to epistemic-graph.

The record vocabulary (``directionalAccuracy``, ``standaloneSharpe``,
``probabilityBacktestOverfit``, ``predictionHorizon``, ``halfLifeDays``) is
declared in ``ontology/trading.ttl`` and stored by epistemic-graph; this module
only shapes the property map a tool writes.
"""

from __future__ import annotations

from typing import Any

#: Node type epistemic-graph stores microstructure signals under.
MICROSTRUCTURE_SIGNAL = "microstructure_signal"


def microstructure_signal_record(
    signal_id: str,
    *,
    name: str = "",
    prediction_horizon: str = "1m",
    directional_accuracy: float = 0.5,
    standalone_sharpe: float = 0.0,
    pbo: float = 0.0,
    decay_regime: str = "stationary",
    half_life_days: float = 0.0,
    provenance: str = "",
    asset_class: str = "equities",
    last_validated: str | None = None,
) -> dict[str, Any]:
    """The property map of one MicrostructureSignal node."""
    if not signal_id:
        raise ValueError("signal_id must not be empty")
    return {
        "id": signal_id,
        "name": name or signal_id,
        "type": MICROSTRUCTURE_SIGNAL,
        "prediction_horizon": prediction_horizon,
        "directional_accuracy": float(directional_accuracy),
        "standalone_sharpe": float(standalone_sharpe),
        "pbo": float(pbo),
        "decay_regime": decay_regime,
        "half_life_days": float(half_life_days),
        "provenance": provenance,
        "asset_class": asset_class,
        "last_validated": last_validated,
    }
