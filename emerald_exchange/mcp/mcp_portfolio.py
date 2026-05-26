"""Portfolio MCP Tools — CONCEPT:EE-010."""

from typing import Any

import json

from emerald_exchange.backends import ExchangeBackend


def register_portfolio_tools(mcp: Any, backend: ExchangeBackend) -> None:

    @mcp.tool(tags=["portfolio"])
    def emerald_portfolio(action: str) -> str:
        """Portfolio management operations. CONCEPT:EE-010

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
