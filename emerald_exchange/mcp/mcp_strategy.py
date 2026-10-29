"""Strategy Management MCP Tools — CONCEPT:AU-AHE.assimilation.trading-ecosystem-spec."""
import json
import logging
from typing import Any


def register_strategy_tools(mcp: Any) -> None:

    @mcp.tool(tags=["strategy"])
    def emerald_strategy(
        action: str,
        strategy_id: str = "",
        format: str = "pinescript",
        returns_json: str = "[]",
        n_trials: int = 1,
        name: str = "",
        prediction_horizon: str = "1m",
    ) -> str:
        """Strategy lifecycle management. CONCEPT:AU-AHE.assimilation.trading-ecosystem-spec

        Actions:
        - 'list': List strategies from KG
        - 'promote': Promote strategy stage (draft->backtest->paper->live)
        - 'export': Export to PineScript/MQL5/TDX
        - 'backtest': Validate a returns series (deflated Sharpe + PBO) and write
          the measured priors back onto the MicrostructureSignal ``strategy_id``
          in the KG, so signal-fusion weights self-adjust (CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion).
        """
        try:
            if action == "backtest":
                from .. import analyses
                from .._engine import finance_engine

                try:
                    returns = [float(x) for x in json.loads(returns_json)]
                except (ValueError, TypeError) as exc:
                    return json.dumps({"error": f"invalid returns_json: {type(exc).__name__}"})
                if len(returns) < 2:
                    return json.dumps({"error": "need >= 2 returns to backtest"})

                metrics = analyses.validate_returns(returns, n_trials=n_trials)
                if "error" in metrics:
                    return json.dumps(metrics)
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
                    from emerald_exchange.signal_records import (
                        microstructure_signal_record,
                    )

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

                return json.dumps(
                    {
                        "strategy_id": strategy_id,
                        "deflated_sharpe": deflated,
                        "hit_rate": hit_rate,
                        "pbo": pbo,
                        "priors_written": written,
                        **{k: v for k, v in metrics.items() if k != "cpcv_splits"},
                    }
                )
            if action == "list":
                return json.dumps(
                    {"strategies": [], "note": "Query KG for TradingStrategy nodes"}
                )
            elif action == "promote":
                return json.dumps(
                    {
                        "strategy_id": strategy_id,
                        "note": "Use strategy_engine.py lifecycle",
                    }
                )
            elif action == "export":
                return json.dumps(
                    {
                        "strategy_id": strategy_id,
                        "format": format,
                        "note": "Use strategy_export.py",
                    }
                )
            return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as caught_error:
            logging.getLogger(__name__).exception("Operation failed (type=%s)", type(caught_error).__name__, exc_info=False)
            return json.dumps({"error": "Operation failed"})
