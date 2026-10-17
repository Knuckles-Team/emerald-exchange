"""Market-Making / Backtest-Validation / Forensic MCP Tools — CONCEPT:EX-AHE.harness.ee-22.

Action-routed tool over epistemic-graph analyses (``ontology/quant.ttl``):
  - quote: intended market-making quotes (decision only, no live order).
  - fee / backtest: refused (not_served) until epistemic-graph serves them.
  - forensic, brier, validate, pbo: served analyses.

CRITICAL SAFETY: the ``quote`` action returns a *decision* (intended bid/ask +
withdraw flag); it never places an order. Live execution stays gated behind
``RiskGuard.require_human_approval_live`` in the order/prediction-market tools.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_market_making_tools(mcp: Any) -> None:
    """Register market-making, fee-model, and forensic-screen tools."""

    @mcp.tool(tags=["market_making"])
    def emerald_market_making(
        action: str,
        params_json: str = "{}",
    ) -> str:
        """Market-making controller, fee model, and forensic screener. CONCEPT:EX-AHE.harness.ee-22

        Actions:
          - 'quote': Compute intended MM quotes for one book update (decision
            only — does NOT place orders). params: book{ts,bid_px,bid_sz,ask_px,
            ask_sz,buy_vol,sell_vol,p_mean}, inventory, signal_strengths (list —
            triggers the CONVICTION GATE, on by default), config{gamma,kappa,
            sigma,tau,tick,bounded,boundary_m,ofi_drift_coef,max_inventory,
            conviction_gate,conviction_strong_threshold,conviction_min_agree}.
          - 'fee': venue fee for a fill — refused (not_served).
          - 'backtest': event-driven L2-queue backtest — refused (not_served).
          - 'validate': performance, deflated Sharpe and purged CPCV of
            backtest returns. params: returns (list), n_trials, cpcv_groups,
            cpcv_test_groups.
          - 'pbo': probability of backtest overfit. params: insample, oos
            (matrices: rows = CV splits, cols = strategies).
          - 'forensic': Two-year forensic accounting screen. params: this_year,
            prior_year (standardized financial line items).
          - 'brier': Brier calibration score of forecasts vs outcomes. params:
            forecasts (list[0,1]), outcomes (list[0/1]).

        Args:
            action: operation to perform.
            params_json: JSON string of parameters.
        """
        try:
            params = json.loads(params_json or "{}")
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"invalid params_json: {type(exc).__name__}"})

        try:
            if action == "quote":
                from emerald_exchange.market_making import (
                    BookSnapshot,
                    MarketMakingController,
                    MMConfig,
                )

                b = params.get("book", {})
                book = BookSnapshot(
                    ts=b.get("ts", []),
                    bid_px=b.get("bid_px", []),
                    bid_sz=b.get("bid_sz", []),
                    ask_px=b.get("ask_px", []),
                    ask_sz=b.get("ask_sz", []),
                    buy_vol=b.get("buy_vol", []),
                    sell_vol=b.get("sell_vol", []),
                    p_mean=b.get("p_mean", []),
                )
                cfg_in = params.get("config", {})
                config = MMConfig(
                    **{
                        k: v
                        for k, v in cfg_in.items()
                        if k in MMConfig.__dataclass_fields__
                    }
                )
                controller = MarketMakingController(config)
                strengths = params.get("signal_strengths")
                strengths = (
                    [float(s) for s in strengths]
                    if isinstance(strengths, list)
                    else None
                )
                decision = controller.decide(
                    book,
                    float(params.get("inventory", 0.0)),
                    signal_strengths=strengths,
                )
                return json.dumps(decision.to_dict())

            from emerald_exchange import analyses

            if action == "fee":
                return json.dumps(
                    analyses.venue_fee(
                        float(params.get("price", 0.5)),
                        float(params.get("size", 0.0)),
                        str(params.get("category", "other")),
                        is_maker=bool(params.get("is_maker", False)),
                    )
                )
            if action == "backtest":
                return json.dumps(analyses.event_backtest(params.get("events", [])))
            if action == "forensic":
                return json.dumps(
                    analyses.forensic_screen(
                        params.get("this_year", {}), params.get("prior_year", {})
                    )
                )
            if action == "brier":
                return json.dumps(
                    analyses.brier_score(
                        params.get("forecasts", []), params.get("outcomes", [])
                    )
                )
            if action == "validate":
                return json.dumps(
                    analyses.validate_returns(
                        [float(x) for x in params.get("returns", [])],
                        n_trials=int(params.get("n_trials", 1)),
                        cpcv_groups=int(params.get("cpcv_groups", 6)),
                        cpcv_test_groups=int(params.get("cpcv_test_groups", 2)),
                    )
                )
            if action == "pbo":
                return json.dumps(
                    analyses.probability_overfit(
                        params.get("insample", []), params.get("oos", [])
                    )
                )
            return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as exc:  # noqa: BLE001
            logger.error("Operation failed: error_type=%s", type(exc).__name__)
            return json.dumps({"error": "Operation failed"})
