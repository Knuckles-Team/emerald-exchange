"""Portfolio MCP Tools — CONCEPT:EX-AHE.harness.ee-9."""

import json
from typing import Any, Literal

from emerald_exchange.backends import AccountInfo, Position, TradingMode
from emerald_exchange.trading.governed import GovernedBackend


def _positions(positions: list[Position]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": p.symbol,
            "qty": p.qty,
            "avg_entry": p.avg_entry_price,
            "current": p.current_price,
            "pnl": p.unrealized_pnl,
            "side": p.side,
            "exchange": p.exchange,
        }
        for p in positions
    ]


def _account(account: AccountInfo) -> dict[str, Any]:
    return {
        "equity": account.equity,
        "cash": account.cash,
        "buying_power": account.buying_power,
        "currency": account.currency,
    }


def positions_snapshot(backend: GovernedBackend) -> dict[str, Any]:
    """Read-only positions for the operator widget (EH-423).

    ``venue`` is the real account read through the venue, never written;
    ``paper`` is the paper account every order in paper mode fills on, with its
    unrealized P&L. Neither half can place an order.
    """
    venue_positions = backend.venue_positions()
    paper_positions = (
        backend.get_positions() if backend.mode == TradingMode.PAPER else []
    )
    return {
        "mode": str(backend.mode),
        "venue_name": backend.name,
        "venue": {
            "account": _account(backend.venue_account()),
            "positions": _positions(venue_positions),
        },
        "paper": {
            "positions": _positions(paper_positions),
            "unrealized_pnl": sum(p.unrealized_pnl for p in paper_positions),
        },
        "informational_only": True,
    }


def register_portfolio_tools(mcp: Any, backend: GovernedBackend) -> None:
    @mcp.tool(tags=["portfolio"])
    def emerald_positions_snapshot() -> str:
        """Read-only positions: the venue account and the paper account (EH-423).

        Never places or cancels anything. CONCEPT:EX-AHE.harness.ee-9
        """
        return json.dumps(positions_snapshot(backend))

    @mcp.tool(
        tags=["portfolio"],
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        meta={
            "eg.annotations": {"modalities_in": ["text"], "modalities_out": ["text"]}
        },
    )
    def emerald_portfolio(action: Literal["account", "positions"]) -> str:
        """Portfolio management operations. CONCEPT:EX-AHE.harness.ee-9

        Actions:
        - 'positions': List all open positions
        - 'account': Get account summary (equity, cash, buying power)
        """
        if action == "positions":
            positions = backend.get_positions()
            return json.dumps(
                [
                    {
                        "symbol": p.symbol,
                        "qty": p.qty,
                        "avg_entry": p.avg_entry_price,
                        "current": p.current_price,
                        "pnl": p.unrealized_pnl,
                        "side": p.side,
                        "exchange": p.exchange,
                    }
                    for p in positions
                ]
            )
        elif action == "account":
            acct = backend.get_account()
            return json.dumps(
                {
                    "equity": acct.equity,
                    "cash": acct.cash,
                    "buying_power": acct.buying_power,
                    "margin_used": acct.margin_used,
                    "currency": acct.currency,
                    "exchange": acct.exchange,
                }
            )
        return json.dumps({"error": f"Unknown action: {action}"})
