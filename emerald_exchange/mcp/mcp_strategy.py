"""Strategy Management MCP Tools — CONCEPT:AU-AHE.assimilation.trading-ecosystem-spec."""

from typing import Any

import json


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
                from ..backtester import probability_overfit, validate_returns
                from .._engine import finance_engine

                try:
                    returns = [float(x) for x in json.loads(returns_json)]
                except (ValueError, TypeError) as exc:
                    return json.dumps({"error": f"invalid returns_json: {exc}"})
                if len(returns) < 2:
                    return json.dumps({"error": "need >= 2 returns to backtest"})

                metrics = validate_returns(returns, n_trials=n_trials)
                if "error" in metrics:
                    return json.dumps(metrics)
                deflated = float(metrics.get("deflated_sharpe", 0.0))
                hit_rate = sum(1 for r in returns if r > 0) / len(returns)
                # Split-half PBO as a lightweight overfit guard on a single series.
                half = len(returns) // 2
                pbo_out = probability_overfit([returns[:half]], [returns[half:]])
                pbo = float(pbo_out.get("pbo", 0.0))

                # Write priors back to the KG (same store the fuse path reads).
                engine = finance_engine()
                written = False
                if engine is not None and strategy_id:
                    from agent_utilities.models.domains.finance import (
                        MicrostructureSignalNode,
                    )

                    node = MicrostructureSignalNode(
                        id=strategy_id,
                        name=name or strategy_id,
                        prediction_horizon=prediction_horizon,
                        directional_accuracy=hit_rate,
                        standalone_sharpe=deflated,
                        pbo=pbo,
                        provenance=f"backtest:{strategy_id}",
                    )
                    try:
                        engine.nodes.add(strategy_id, node.model_dump(mode="json"))
                        written = True
                    except Exception as exc:  # noqa: BLE001 — degrade, still report
                        metrics["write_error"] = str(exc)

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
        except Exception as e:
            return json.dumps({"error": str(e)})
