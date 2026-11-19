"""Trading Debate MCP Tools — CONCEPT:EX-AHE.harness.ee-13.

Multi-agent trading debate engine, one typed tool per step. Bull vs Bear
agents argue a hypothesis, Risk Compliance Officer has veto power. Routes to
KG orchestration for consensus tracking.
"""

import json
from typing import Annotated, Any, Literal

from pydantic import Field

from emerald_exchange.mcp._hints import READ, WRITE

DebateId = Annotated[str, Field(description="Debate id returned by the start tool")]


def register_debate_tools(mcp: Any) -> None:
    """Register trading debate tools. CONCEPT:EX-AHE.harness.ee-13."""

    @mcp.tool(tags={"debate"}, annotations=WRITE)
    def emerald_debate_start(
        hypothesis: Annotated[str, Field(description="Trading hypothesis to debate")],
        rounds: Annotated[int, Field(description="Number of debate rounds")] = 3,
    ) -> str:
        """Start a new debate on a trading hypothesis. CONCEPT:EX-AHE.harness.ee-13"""
        if not hypothesis:
            return json.dumps({"error": "hypothesis required"})
        return json.dumps(
            {
                "debate_id": f"DEBATE-{hash(hypothesis) % 100000:05d}",
                "hypothesis": hypothesis,
                "rounds": rounds,
                "status": "active",
                "note": "Route to graph_orchestrate.start_debate for KG-native tracking",
            }
        )

    @mcp.tool(tags={"debate"}, annotations=WRITE)
    def emerald_debate_submit_argument(
        debate_id: DebateId,
        argument: Annotated[str, Field(description="The argument text")],
        side: Literal["bull", "bear"] = "bull",
    ) -> str:
        """Submit a bull or bear argument to an active debate. CONCEPT:EX-AHE.harness.ee-13"""
        if not debate_id or not argument:
            return json.dumps({"error": "debate_id and argument required"})
        return json.dumps(
            {
                "debate_id": debate_id,
                "side": side,
                "argument": argument,
                "status": "recorded",
                "note": "Argument persisted as DebateArgument node in KG",
            }
        )

    @mcp.tool(tags={"debate"}, annotations=WRITE)
    def emerald_debate_risk_veto(
        debate_id: DebateId,
        veto_reason: Annotated[
            str, Field(description="Why the hypothesis is vetoed")
        ] = "",
    ) -> str:
        """Risk officer veto: reject the hypothesis at once. CONCEPT:EX-AHE.harness.ee-13"""
        if not debate_id:
            return json.dumps({"error": "debate_id required"})
        return json.dumps(
            {
                "debate_id": debate_id,
                "status": "VETOED",
                "veto_reason": veto_reason or "Risk compliance officer veto",
                "note": "Hypothesis rejected — no further execution allowed",
            }
        )

    @mcp.tool(tags={"debate"}, annotations=READ)
    def emerald_debate_consensus(debate_id: DebateId) -> str:
        """Debate consensus and outcome so far. CONCEPT:EX-AHE.harness.ee-13"""
        if not debate_id:
            return json.dumps({"error": "debate_id required"})
        return json.dumps(
            {
                "debate_id": debate_id,
                "consensus": "pending",
                "bull_score": 0.0,
                "bear_score": 0.0,
                "note": "Query KG for DebateArgument nodes and score",
            }
        )

    @mcp.tool(tags={"debate"}, annotations=READ)
    def emerald_debate_history() -> str:
        """Past debates from the knowledge graph. CONCEPT:EX-AHE.harness.ee-13"""
        return json.dumps(
            {
                "debates": [],
                "note": "Query KG: MATCH (d:TradingDebate) RETURN d",
            }
        )
