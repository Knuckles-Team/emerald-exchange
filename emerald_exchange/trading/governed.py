"""The one backend the MCP surface sees: read-only venue, paper effects (EH-423).

A venue backend (Alpaca, CCXT, Polymarket, ...) can place real orders. This
wrapper is the chokepoint that keeps that capability out of reach:

* Reads -- positions, account, quote, history, order status -- go to the venue.
  In ``live`` mode ``get_positions``/``get_account`` are the real account,
  read-only.
* Effects -- ``submit_order``/``cancel_order`` -- go to a paper account in
  ``paper`` mode (the default). It is the venue's own paper endpoint when the
  venue is in paper mode, otherwise a local simulator priced by the venue's
  quotes. In ``live`` mode every effect is refused: a live order exists only
  as an approved D18 change set applied by
  :func:`emerald_exchange.trading.live_orders.execute_approved_order`.

Nothing here takes an "approved" flag. A boolean any caller can pass is not an
approval; the approval is a durable EG record a person made at the operator
console.
"""

from __future__ import annotations

from emerald_exchange.backends import (
    OHLCV,
    AccountInfo,
    ExchangeBackend,
    ExecutionResult,
    OrderSide,
    OrderType,
    PaperBackend,
    Position,
    Quote,
    TradingMode,
)

__all__ = ["LIVE_ORDER_GUIDANCE", "GovernedBackend", "LiveOrderRefused"]

#: What a refused live effect tells its caller to do instead.
LIVE_ORDER_GUIDANCE = (
    "Live orders are placed only through an approved D18 change set: propose "
    "the order with graph-os `graph_finance` action `propose_order`, have a person approve it "
    "at the operator console, then run `emerald_live_orders("
    "action='execute_approved', approval_id=...)`."
)


class LiveOrderRefused(PermissionError):
    """A live order or cancel was attempted outside the approved D18 path."""


class GovernedBackend:
    """Read the venue; trade on paper; never place a live effect directly."""

    def __init__(
        self,
        venue: ExchangeBackend,
        mode: TradingMode = TradingMode.PAPER,
        *,
        initial_paper_cash: float = 100_000.0,
    ) -> None:
        self._venue = venue
        self._mode = TradingMode(mode)
        venue_is_paper = venue.mode == TradingMode.PAPER
        self._paper: ExchangeBackend = (
            venue
            if venue_is_paper
            else PaperBackend(initial_cash=initial_paper_cash, price_source=venue)
        )

    @property
    def name(self) -> str:
        return self._venue.name

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def supported_assets(self) -> list[str]:
        return self._venue.supported_assets

    def connect(self) -> bool:
        return self._venue.connect()

    def disconnect(self) -> None:
        self._venue.disconnect()

    def _refuse_live(self, what: str) -> None:
        if self._mode == TradingMode.LIVE:
            raise LiveOrderRefused(
                f"{what} refused in live mode. {LIVE_ORDER_GUIDANCE}"
            )

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
    ) -> ExecutionResult:
        """Paper-fill the order; refuse in live mode."""
        self._refuse_live("submit_order")
        return self._paper.submit_order(symbol, side, qty, order_type, limit_price)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order; refuse in live mode."""
        self._refuse_live("cancel_order")
        return self._paper.cancel_order(order_id)

    def get_order_status(self, order_id: str) -> ExecutionResult:
        return self._account_source().get_order_status(order_id)

    def get_positions(self) -> list[Position]:
        """Paper positions in paper mode; the real account, read-only, in live."""
        return self._account_source().get_positions()

    def get_account(self) -> AccountInfo:
        return self._account_source().get_account()

    def venue_positions(self) -> list[Position]:
        """The venue account's positions, read-only, whatever the mode."""
        return self._venue.get_positions()

    def venue_account(self) -> AccountInfo:
        """The venue account summary, read-only, whatever the mode."""
        return self._venue.get_account()

    def get_quote(self, symbol: str) -> Quote:
        return self._venue.get_quote(symbol)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        return self._venue.get_historical(symbol, period, interval)

    def _account_source(self) -> ExchangeBackend:
        return self._venue if self._mode == TradingMode.LIVE else self._paper
