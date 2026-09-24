"""Live order execution MCP tool — the approved D18 path only (EH-423).

Registered only when the server runs in ``live`` mode. It takes an approval id
and nothing else: the order it places is the one a person approved at the
graph-os operator console, read back from EG, and it is placed at most once.
An agent calling it can only execute what a person already approved.
"""

from __future__ import annotations

import json
from typing import Any

from agent_connector_sdk.writeback.epistemic_graph import (
    EpistemicGraphWriteBackLedger,
)
from agent_connector_sdk.writeback.errors import WriteBackError

from emerald_exchange._engine import (
    EngineIdentityMissing,
    engine_endpoint,
    live_order_auth_secret,
    live_order_context,
)
from emerald_exchange.backends import ExchangeBackend
from emerald_exchange.trading.live_orders import (
    ApprovalRefused,
    execute_approved_order,
)

__all__ = ["register_live_order_tools"]


def _refused(reason: str) -> str:
    return json.dumps({"status": "refused", "reason": reason})


async def _execute(venue: ExchangeBackend, approval_id: str) -> dict[str, Any]:
    from epistemic_graph.client import EpistemicGraphClient

    context = live_order_context()
    endpoint = engine_endpoint()
    connect = EpistemicGraphClient.connect(
        socket_path=endpoint.get("socket_path"),
        tcp_addr=endpoint.get("tcp_addr"),
        auth_secret=live_order_auth_secret(),
        graph_name=str(context["tenant"]),
        verified_context=context,
    )
    async with await connect as client:
        return await execute_approved_order(
            approval_id,
            tenant=str(context["tenant"]),
            venue=venue,
            ledger=EpistemicGraphWriteBackLedger(client),
            leases=client.control_leases,
        )


def register_live_order_tools(mcp: Any, venue: ExchangeBackend) -> None:
    """Register ``emerald_live_orders`` over the raw venue (live mode only)."""

    @mcp.tool(tags=["orders"])
    async def emerald_live_orders(action: str, approval_id: str = "") -> str:
        """Place a human-approved live order. CONCEPT:EX-AHE.harness.ee-8

        Actions:
        - 'execute_approved': place the order the approval ``approval_id``
          authorised, once. Refused unless a person approved exactly this
          order at the graph-os operator console and the approval is live.
        """
        if action != "execute_approved":
            return json.dumps({"error": f"Unknown action: {action}"})
        if not approval_id:
            return _refused("approval_id is required")
        try:
            result = await _execute(venue, approval_id)
        except (ApprovalRefused, EngineIdentityMissing, WriteBackError) as exc:
            return _refused(str(exc))
        return json.dumps({"status": "ok", **result})
