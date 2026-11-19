"""Strategy Management MCP Tools — CONCEPT:AU-AHE.assimilation.trading-ecosystem-spec.

One typed tool per strategy lifecycle operation.
"""

import json
import logging
from typing import Annotated, Any, Literal

from pydantic import Field

from emerald_exchange.mcp._hints import READ, WRITE

logger = logging.getLogger(__name__)

StrategyId = Annotated[str, Field(description="Strategy id")]


def _backtest(
    returns: list[float],
    strategy_id: str,
    n_trials: int,
    name: str,
    prediction_horizon: str,
) -> dict[str, Any]:
    from emerald_exchange import analyses
    from emerald_exchange._engine import finance_engine

    if len(returns) < 2:
        return {"error": "need >= 2 returns to backtest"}

    metrics = analyses.validate_returns(returns, n_trials=n_trials)
    if "error" in metrics:
        return metrics
    deflated = metrics.get("deflated_sharpe")
    hit = analyses.hit_rate(returns)
    hit_rate = hit.get("hit_rate", hit)
    # Split-half PBO as a lightweight overfit guard on a single series.
    half = len(returns) // 2
    pbo_out = analyses.probability_overfit([returns[:half]], [returns[half:]])
    pbo = pbo_out.get("pbo", pbo_out)
    measured = all(isinstance(v, float) for v in (deflated, hit_rate, pbo))

    # Write priors back to the KG (same store the fuse path reads).
    engine = finance_engine()
    written = False
    if engine is not None and strategy_id and measured:
        from emerald_exchange.signal_records import microstructure_signal_record

        record = microstructure_signal_record(
            strategy_id,
            name=name or strategy_id,
            prediction_horizon=prediction_horizon,
            directional_accuracy=hit_rate,
            standalone_sharpe=deflated,
            pbo=pbo,
            provenance=f"backtest:{strategy_id}",
        )
        try:
            engine.nodes.add(strategy_id, record)
            written = True
        except Exception as exc:  # noqa: BLE001 — degrade, still report
            metrics["write_error"] = type(exc).__name__

    return {
        "strategy_id": strategy_id,
        "deflated_sharpe": deflated,
        "hit_rate": hit_rate,
        "pbo": pbo,
        "priors_written": written,
        **{k: v for k, v in metrics.items() if k != "cpcv_splits"},
    }


def register_strategy_tools(mcp: Any) -> None:
    """Register the strategy lifecycle tools."""

    @mcp.tool(tags={"strategy"}, annotations=WRITE)
    def emerald_strategy_backtest(
        returns: Annotated[list[float], Field(description="Strategy return series")],
        strategy_id: Annotated[
            str, Field(description="MicrostructureSignal id that receives the priors")
        ] = "",
        n_trials: Annotated[int, Field(description="Strategies tried")] = 1,
        name: Annotated[str, Field(description="Signal display name")] = "",
        prediction_horizon: Annotated[
            str, Field(description="Prediction horizon, for example 1m")
        ] = "1m",
    ) -> str:
        """Validate a returns series (deflated Sharpe + PBO) and write the priors.

        The measured priors land on the MicrostructureSignal ``strategy_id`` in
        the KG, so signal-fusion weights self-adjust
        (CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion).
        """
        try:
            return json.dumps(
                _backtest(returns, strategy_id, n_trials, name, prediction_horizon)
            )
        except Exception as caught_error:
            logger.error("Operation failed (type=%s)", type(caught_error).__name__)
            return json.dumps({"error": "Operation failed"})

    @mcp.tool(tags={"strategy"}, annotations=READ)
    def emerald_strategy_list() -> str:
        """Strategies from the knowledge graph. CONCEPT:AU-AHE.assimilation.trading-ecosystem-spec"""
        return json.dumps(
            {"strategies": [], "note": "Query KG for TradingStrategy nodes"}
        )

    @mcp.tool(tags={"strategy"}, annotations=WRITE)
    def emerald_strategy_promote(strategy_id: StrategyId) -> str:
        """Promote a strategy stage (draft -> backtest -> paper -> live)."""
        return json.dumps(
            {
                "strategy_id": strategy_id,
                "note": "Use strategy_engine.py lifecycle",
            }
        )

    @mcp.tool(tags={"strategy"}, annotations=READ)
    def emerald_strategy_export(
        strategy_id: StrategyId,
        format: Literal["pinescript", "mql5", "tdx"] = "pinescript",
    ) -> str:
        """Export a strategy to PineScript, MQL5 or TDX."""
        return json.dumps(
            {
                "strategy_id": strategy_id,
                "format": format,
                "note": "Use strategy_export.py",
            }
        )
