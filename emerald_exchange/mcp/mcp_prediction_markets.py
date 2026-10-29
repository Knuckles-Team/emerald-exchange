"""Prediction Markets MCP Domain — CONCEPT:EX-AHE.harness.ee-8

Action-routed tool for Kalshi, Polymarket, and Open-Meteo ensemble forecasts.
"""

import json
import logging
from typing import Any

import httpx
from agent_connector_sdk.compute import MethodNotServedError

from emerald_exchange.risk_guards import RiskGuard

logger = logging.getLogger(__name__)


def register_prediction_market_tools(mcp: Any, risk_guard: RiskGuard | None = None) -> None:
    """Register prediction market tools with the MCP server."""

    @mcp.tool()
    async def ee_prediction_markets(
        action: str,
        params_json: str = "{}",
    ) -> str:
        """Prediction Markets operations.

        Actions:
          - fetch_open_meteo_ensemble: Fetch 31-member ensemble weather forecast.
          - fetch_polymarket_orderbook: Fetch Polymarket orderbook for an event (simulated via API).
          - fetch_kalshi_orderbook: Fetch Kalshi orderbook for an event (simulated via API).
          - evaluate_event_arbitrage: Run dual-platform arbitrage evaluation using Laplace smoothed forecast.

        Args:
            action: The operation to perform.
            params_json: JSON string containing parameters.
        """
        params = json.loads(params_json)

        try:
            if action == "fetch_open_meteo_ensemble":
                latitude = params.get("latitude", 40.7128)
                longitude = params.get("longitude", -74.0060)

                # Fetching 31 members requires multiple models in Open-Meteo or specific ensemble endpoints
                url = f"https://ensemble-api.open-meteo.com/v1/ensemble?latitude={latitude}&longitude={longitude}&hourly=temperature_2m&models=gfs_seamless"
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return json.dumps(response.json())

            elif action == "fetch_polymarket_orderbook":
                # Simulated Polymarket endpoint interaction
                event_id = params.get("event_id")
                # Real implementation would use py_clob_client or raw requests here
                return json.dumps({"platform": "polymarket", "event_id": event_id, "yes_price": 0.55, "no_price": 0.45})

            elif action == "fetch_kalshi_orderbook":
                # Simulated Kalshi endpoint interaction
                ticker = params.get("ticker")
                return json.dumps({"platform": "kalshi", "ticker": ticker, "yes_price": 0.58, "no_price": 0.42})

            elif action == "evaluate_event_arbitrage":
                condition_met_count = params.get("condition_met_count", 0)
                total_members = params.get("total_members", 31)
                pm_price = params.get("polymarket_price", 0.5)
                kalshi_price = params.get("kalshi_price", 0.5)

                # Use default risk limits or explicit threshold
                pm_threshold = 0.08
                kalshi_threshold = 0.08
                if risk_guard and risk_guard.limits:
                    pm_threshold = risk_guard.limits.prediction_market_cost_thresholds.get("polymarket", 0.08)
                    kalshi_threshold = risk_guard.limits.prediction_market_cost_thresholds.get("kalshi", 0.08)

                from emerald_exchange._engine import (
                    ENGINE_REQUIRED_ERR,
                    QUANT_VOCABULARY,
                    analysis_iri,
                    finance_compute,
                )

                compute = finance_compute()
                if compute is None:
                    return json.dumps({"error": ENGINE_REQUIRED_ERR})
                # Epistemic-graph selects and runs the ensemble-probability and
                # edge-threshold algorithm; it is refused until EG serves it.
                try:
                    return json.dumps(
                        compute.analyse(
                            analysis_iri("EnsembleProbabilityAnalysis"),
                            vocabulary=QUANT_VOCABULARY,
                            condition_met_count=int(condition_met_count),
                            total_members=int(total_members),
                            prices={"polymarket": pm_price, "kalshi": kalshi_price},
                            cost_thresholds={
                                "polymarket": pm_threshold,
                                "kalshi": kalshi_threshold,
                            },
                        )
                    )
                except MethodNotServedError as exc:
                    return json.dumps(
                        {
                            "error": "not_served",
                            "action": action,
                            "method": exc.method,
                        }
                    )

            else:
                return json.dumps({"error": f"Unknown action: {action}"})

        except Exception as e:
            logging.getLogger(__name__).exception("Operation failed (type=%s)", type(e).__name__, exc_info=False)
            logger.error("Operation failed: error_type=%s", type(e).__name__)
            return json.dumps({"error": "Operation failed"})
