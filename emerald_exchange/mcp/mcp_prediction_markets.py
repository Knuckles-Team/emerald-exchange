"""Prediction Markets MCP Domain — CONCEPT:EX-AHE.harness.ee-8

One typed tool per operation for Kalshi, Polymarket, and Open-Meteo ensemble
forecasts.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import httpx
from pydantic import Field
from scion_sdk.compute import MethodNotServedError

from emerald_exchange.mcp._hints import READ
from emerald_exchange.risk_guards import RiskGuard

logger = logging.getLogger(__name__)


async def _run(operation: Callable[[], Awaitable[Any]]) -> str:
    try:
        return json.dumps(await operation())
    except Exception as e:
        logger.error("Operation failed: error_type=%s", type(e).__name__)
        return json.dumps({"error": "Operation failed"})


def register_prediction_market_tools(
    mcp: Any, risk_guard: RiskGuard | None = None
) -> None:
    """Register prediction market tools with the MCP server."""

    @mcp.tool(tags={"prediction_market"}, annotations=READ)
    async def emerald_prediction_markets_fetch_open_meteo_ensemble(
        latitude: Annotated[float, Field(description="Latitude in degrees")] = 40.7128,
        longitude: Annotated[
            float, Field(description="Longitude in degrees")
        ] = -74.0060,
    ) -> str:
        """Fetch the 31-member ensemble weather forecast for a location."""

        async def fetch() -> Any:
            # Fetching 31 members requires multiple models in Open-Meteo or specific ensemble endpoints
            url = f"https://ensemble-api.open-meteo.com/v1/ensemble?latitude={latitude}&longitude={longitude}&hourly=temperature_2m&models=gfs_seamless"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()

        return await _run(fetch)

    @mcp.tool(tags={"prediction_market"}, annotations=READ)
    async def emerald_prediction_markets_fetch_polymarket_orderbook(
        event_id: Annotated[str, Field(description="Polymarket event id")],
    ) -> str:
        """Fetch the Polymarket orderbook for an event (simulated via API)."""
        # Real implementation would use py_clob_client or raw requests here
        return json.dumps(
            {
                "platform": "polymarket",
                "event_id": event_id,
                "yes_price": 0.55,
                "no_price": 0.45,
            }
        )

    @mcp.tool(tags={"prediction_market"}, annotations=READ)
    async def emerald_prediction_markets_fetch_kalshi_orderbook(
        ticker: Annotated[str, Field(description="Kalshi market ticker")],
    ) -> str:
        """Fetch the Kalshi orderbook for an event (simulated via API)."""
        return json.dumps(
            {
                "platform": "kalshi",
                "ticker": ticker,
                "yes_price": 0.58,
                "no_price": 0.42,
            }
        )

    @mcp.tool(tags={"prediction_market"}, annotations=READ)
    async def emerald_prediction_markets_evaluate_event_arbitrage(
        condition_met_count: Annotated[
            int, Field(description="Ensemble members meeting the event condition")
        ] = 0,
        total_members: Annotated[int, Field(description="Ensemble size")] = 31,
        polymarket_price: Annotated[
            float, Field(description="Polymarket YES price")
        ] = 0.5,
        kalshi_price: Annotated[float, Field(description="Kalshi YES price")] = 0.5,
    ) -> str:
        """Dual-platform arbitrage evaluation using a Laplace-smoothed forecast."""
        # Use default risk limits or explicit threshold
        pm_threshold = 0.08
        kalshi_threshold = 0.08
        if risk_guard and risk_guard.limits:
            thresholds = risk_guard.limits.prediction_market_cost_thresholds
            pm_threshold = thresholds.get("polymarket", 0.08)
            kalshi_threshold = thresholds.get("kalshi", 0.08)

        from emerald_exchange._engine import (
            ENGINE_REQUIRED_ERR,
            QUANT_VOCABULARY,
            analysis_iri,
            finance_compute,
        )

        async def evaluate() -> Any:
            compute = finance_compute()
            if compute is None:
                return {"error": ENGINE_REQUIRED_ERR}
            # Medulla selects and runs the ensemble-probability and
            # edge-threshold algorithm; it is refused until EG serves it.
            try:
                return compute.analyse(
                    analysis_iri("EnsembleProbabilityAnalysis"),
                    vocabulary=QUANT_VOCABULARY,
                    condition_met_count=condition_met_count,
                    total_members=total_members,
                    prices={"polymarket": polymarket_price, "kalshi": kalshi_price},
                    cost_thresholds={
                        "polymarket": pm_threshold,
                        "kalshi": kalshi_threshold,
                    },
                )
            except MethodNotServedError as exc:
                return {
                    "error": "not_served",
                    "operation": "evaluate_event_arbitrage",
                    "method": exc.method,
                }

        return await _run(evaluate)
