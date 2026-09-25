"""Governed trading: paper by default, live orders only through D18 (EH-423).

Every tool, bridge and verbose MCP surface holds a
:class:`~emerald_exchange.trading.governed.GovernedBackend`, never a venue
backend. The governed backend reads positions, accounts, quotes and history
from the venue, simulates orders on a paper account priced by that venue, and
refuses every live effect. The only code that can place a live order is
:mod:`emerald_exchange.trading.live_orders`, which applies one human-approved
EG ``WriteBack`` change set under its ``action.approval`` lease.
"""

from emerald_exchange.trading.governed import GovernedBackend, LiveOrderRefused

__all__ = ["GovernedBackend", "LiveOrderRefused"]
