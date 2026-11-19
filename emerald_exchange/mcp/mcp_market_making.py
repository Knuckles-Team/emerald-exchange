"""Market-Making / Backtest-Validation / Forensic MCP Tools — CONCEPT:EX-AHE.harness.ee-22.

One typed tool per medulla analysis (``ontology/quant.ttl``):
  - quote: intended market-making quotes (decision only, no live order).
  - fee / backtest: refused (not_served) until medulla serves them.
  - forensic, brier, validate, pbo: served analyses.

CRITICAL SAFETY: the quote tool returns a *decision* (intended bid/ask +
withdraw flag); it never places an order. Live execution stays gated behind
``RiskGuard.require_human_approval_live`` in the order/prediction-market tools.
"""

import json
import logging
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import Field

from emerald_exchange.mcp._hints import READ

logger = logging.getLogger(__name__)

Matrix = Annotated[
    list[list[float]],
    Field(description="Rows are cross-validation splits, columns are strategies"),
]
LineItems = Annotated[
    dict[str, float], Field(description="Standardized financial line items")
]


def _run(compute: Callable[[], Any]) -> str:
    try:
        return json.dumps(compute())
    except Exception as exc:  # noqa: BLE001
        logger.error("Operation failed: error_type=%s", type(exc).__name__)
        return json.dumps({"error": "Operation failed"})


def _quote(
    book: dict[str, list[float]],
    inventory: float,
    signal_strengths: list[float] | None,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    from emerald_exchange.market_making import (
        BookSnapshot,
        MarketMakingController,
        MMConfig,
    )

    snapshot = BookSnapshot(
        ts=book.get("ts", []),
        bid_px=book.get("bid_px", []),
        bid_sz=book.get("bid_sz", []),
        ask_px=book.get("ask_px", []),
        ask_sz=book.get("ask_sz", []),
        buy_vol=book.get("buy_vol", []),
        sell_vol=book.get("sell_vol", []),
        p_mean=book.get("p_mean", []),
    )
    settings = MMConfig(
        **{
            k: v
            for k, v in (config or {}).items()
            if k in MMConfig.__dataclass_fields__
        }
    )
    decision = MarketMakingController(settings).decide(
        snapshot, inventory, signal_strengths=signal_strengths
    )
    return decision.to_dict()


def register_market_making_tools(mcp: Any) -> None:
    """Register market-making, fee-model, and forensic-screen tools."""
    from emerald_exchange import analyses

    @mcp.tool(tags={"market_making"}, annotations=READ)
    def emerald_market_making_quote(
        book: Annotated[
            dict[str, list[float]],
            Field(
                description="Book window: ts, bid_px, bid_sz, ask_px, ask_sz, "
                "buy_vol, sell_vol, p_mean"
            ),
        ],
        inventory: Annotated[float, Field(description="Current inventory")] = 0.0,
        signal_strengths: Annotated[
            list[float] | None,
            Field(
                description="Signal strengths for the conviction gate (on by default)"
            ),
        ] = None,
        config: Annotated[
            dict[str, Any] | None,
            Field(
                description="Quoting policy: gamma, kappa, sigma, tau, tick, bounded, "
                "boundary_m, ofi_drift_coef, max_inventory, conviction_gate, "
                "conviction_strong_threshold, conviction_min_agree"
            ),
        ] = None,
    ) -> str:
        """Intended market-making quotes for one book update (decision only).

        Does NOT place orders. CONCEPT:EX-AHE.harness.ee-22
        """
        return _run(lambda: _quote(book, inventory, signal_strengths, config))

    @mcp.tool(tags={"market_making"}, annotations=READ)
    def emerald_market_making_fee(
        price: Annotated[float, Field(description="Fill price")] = 0.5,
        size: Annotated[float, Field(description="Fill size")] = 0.0,
        category: Annotated[str, Field(description="Market category")] = "other",
        is_maker: Annotated[bool, Field(description="Maker (true) or taker")] = False,
    ) -> str:
        """Venue fee for a fill — refused (not_served). CONCEPT:EX-AHE.harness.ee-22"""
        return _run(
            lambda: analyses.venue_fee(price, size, category, is_maker=is_maker)
        )

    @mcp.tool(tags={"market_making"}, annotations=READ)
    def emerald_market_making_backtest(
        events: Annotated[
            list[dict[str, Any]], Field(description="L2 book and trade events")
        ],
    ) -> str:
        """Event-driven L2-queue backtest — refused (not_served). CONCEPT:EX-AHE.harness.ee-22"""
        return _run(lambda: analyses.event_backtest(events))

    @mcp.tool(tags={"market_making"}, annotations=READ)
    def emerald_market_making_forensic(
        this_year: LineItems, prior_year: LineItems
    ) -> str:
        """Two-year forensic accounting screen. CONCEPT:EX-AHE.harness.ee-22"""
        return _run(lambda: analyses.forensic_screen(this_year, prior_year))

    @mcp.tool(tags={"market_making"}, annotations=READ)
    def emerald_market_making_brier(
        forecasts: Annotated[list[float], Field(description="Forecasts in [0, 1]")],
        outcomes: Annotated[list[float], Field(description="Outcomes, 0 or 1")],
    ) -> str:
        """Brier calibration score of forecasts vs outcomes. CONCEPT:EX-AHE.harness.ee-22"""
        return _run(lambda: analyses.brier_score(forecasts, outcomes))

    @mcp.tool(tags={"market_making"}, annotations=READ)
    def emerald_market_making_validate(
        returns: Annotated[list[float], Field(description="Backtest returns")],
        n_trials: Annotated[int, Field(description="Strategies tried")] = 1,
        cpcv_groups: Annotated[int, Field(description="CPCV groups")] = 6,
        cpcv_test_groups: Annotated[int, Field(description="CPCV test groups")] = 2,
    ) -> str:
        """Performance, deflated Sharpe and purged CPCV of backtest returns. CONCEPT:EX-AHE.harness.ee-22"""
        return _run(
            lambda: analyses.validate_returns(
                returns,
                n_trials=n_trials,
                cpcv_groups=cpcv_groups,
                cpcv_test_groups=cpcv_test_groups,
            )
        )

    @mcp.tool(tags={"market_making"}, annotations=READ)
    def emerald_market_making_pbo(insample: Matrix, oos: Matrix) -> str:
        """Probability of backtest overfit. CONCEPT:EX-AHE.harness.ee-22"""
        return _run(lambda: analyses.probability_overfit(insample, oos))
