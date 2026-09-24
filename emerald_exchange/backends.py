"""Exchange Backend Abstractions — CONCEPT:EX-AHE.harness.ee

Unified Protocol for all exchange implementations.
Backends: Paper (default), Alpaca, Binance, IBKR, Freqtrade, CCXT.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class UnsupportedIntervalError(ValueError):
    """A caller asked for an OHLCV interval this backend/exchange does not support.

    Never silently substitute a different interval (e.g. daily bars) for one a
    caller explicitly requested — CONCEPT:EX-AHE.harness.ee-4 fail-loud contract.
    """


class HistoricalDataError(RuntimeError):
    """Historical OHLCV data could not be retrieved from the backend.

    Raised instead of returning an empty/partial result, so a data-source
    failure is never mistaken for "the asset has no history".
    """


#: Unified ccxt timeframe strings this backend accepts, in ascending order.
#: A specific exchange may support a subset; ``CCXTBackend.get_historical``
#: intersects this with the connected exchange's own ``.timeframes`` (when the
#: exchange publishes one) before accepting a request.
CCXT_TIMEFRAMES: tuple[str, ...] = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
)

#: Milliseconds per unit, used to advance the pagination cursor and to size
#: the lookback window from a ``period`` string.
_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 3_600_000,
    "2h": 2 * 3_600_000,
    "4h": 4 * 3_600_000,
    "6h": 6 * 3_600_000,
    "8h": 8 * 3_600_000,
    "12h": 12 * 3_600_000,
    "1d": 86_400_000,
    "3d": 3 * 86_400_000,
    "1w": 7 * 86_400_000,
    "1M": 30 * 86_400_000,
}

#: Maximum OHLCV pages fetched for one ``get_historical`` call — a safety cap,
#: not a silent truncation: hitting it raises ``HistoricalDataError`` instead
#: of returning a quietly short result.
MAX_HISTORICAL_PAGES = 200


def _period_to_lookback_ms(period: str) -> int:
    """Parse a yfinance-style period string (``"30d"``, ``"6mo"``, ``"1y"``, ``"max"``).

    Raises:
        ValueError: the period string has no recognized suffix.
    """
    if period == "max":
        return 10 * 365 * 86_400_000
    normalized = period.strip().lower()
    for suffix, unit_days in (("mo", 30), ("d", 1), ("w", 7), ("y", 365)):
        if normalized.endswith(suffix):
            digits = normalized[: -len(suffix)]
            if digits.isdigit() and digits:
                return int(digits) * unit_days * 86_400_000
    raise ValueError(
        f"unrecognized period {period!r}: expected e.g. '30d', '6mo', '1y', 'max'"
    )


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


@dataclass
class ExecutionResult:
    order_id: str
    status: OrderStatus
    filled_qty: float
    average_price: float
    fees: float
    exchange: str
    timestamp: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    side: str
    exchange: str


@dataclass
class AccountInfo:
    equity: float
    cash: float
    buying_power: float
    margin_used: float = 0.0
    currency: str = "USD"
    exchange: str = ""


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: str = ""


@dataclass
class OHLCV:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@runtime_checkable
class ExchangeBackend(Protocol):
    """Abstracted exchange interface — CONCEPT:EX-AHE.harness.ee."""

    @property
    def name(self) -> str: ...
    @property
    def mode(self) -> TradingMode: ...
    @property
    def supported_assets(self) -> list[str]: ...

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
    ) -> ExecutionResult: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def get_order_status(self, order_id: str) -> ExecutionResult: ...
    def get_positions(self) -> list[Position]: ...
    def get_account(self) -> AccountInfo: ...
    def get_quote(self, symbol: str) -> Quote: ...
    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]: ...


class PaperBackend:
    """Local simulation backend — DEFAULT for all trading. CONCEPT:EX-AHE.harness.ee-2."""

    def __init__(self, initial_cash: float = 100000.0):
        self._cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, ExecutionResult] = {}
        self._order_counter = 0

    @property
    def name(self) -> str:
        return "paper"

    @property
    def mode(self) -> TradingMode:
        return TradingMode.PAPER

    @property
    def supported_assets(self) -> list[str]:
        return ["equity", "crypto", "forex"]

    def connect(self) -> bool:
        logger.info("Paper backend connected (simulated)")
        return True

    def disconnect(self) -> None:
        logger.info("Paper backend disconnected")

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
    ) -> ExecutionResult:
        self._order_counter += 1
        oid = f"PAPER-{self._order_counter:06d}"
        price = limit_price or 100.0  # Placeholder
        fees = price * qty * 0.001
        result = ExecutionResult(
            order_id=oid,
            status=OrderStatus.FILLED,
            filled_qty=qty,
            average_price=price,
            fees=fees,
            exchange="paper",
        )
        self._orders[oid] = result
        # Update position
        if symbol in self._positions:
            pos = self._positions[symbol]
            if side == OrderSide.BUY:
                total_cost = pos.avg_entry_price * pos.qty + price * qty
                pos.qty += qty
                pos.avg_entry_price = total_cost / pos.qty if pos.qty else 0
            else:
                pos.qty -= qty
                if pos.qty <= 0:
                    del self._positions[symbol]
        elif side == OrderSide.BUY:
            self._positions[symbol] = Position(
                symbol=symbol,
                qty=qty,
                avg_entry_price=price,
                current_price=price,
                unrealized_pnl=0.0,
                side="long",
                exchange="paper",
            )
        self._cash -= (
            (price * qty + fees) if side == OrderSide.BUY else -(price * qty - fees)
        )
        logger.info("Paper order %s: %s %s %.2f @ %.2f", oid, side, symbol, qty, price)
        return result

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    def get_order_status(self, order_id: str) -> ExecutionResult:
        if order_id in self._orders:
            return self._orders[order_id]
        return ExecutionResult(
            order_id=order_id,
            status=OrderStatus.REJECTED,
            filled_qty=0,
            average_price=0,
            fees=0,
            exchange="paper",
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def get_account(self) -> AccountInfo:
        equity = self._cash + sum(
            p.qty * p.current_price for p in self._positions.values()
        )
        return AccountInfo(
            equity=equity, cash=self._cash, buying_power=self._cash, exchange="paper"
        )

    def get_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, bid=99.99, ask=100.01, last=100.0, volume=1000000)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        return []


class AlpacaBackend:
    """Alpaca Markets backend — FREE paper + live equities. CONCEPT:EX-AHE.harness.ee-3."""

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        base_url: str = "https://paper-api.alpaca.markets",
        mode: TradingMode = TradingMode.PAPER,
    ):
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url
        self._mode = mode
        self._client: Any = None

    @property
    def name(self) -> str:
        return "alpaca"

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def supported_assets(self) -> list[str]:
        return ["equity", "crypto"]

    def connect(self) -> bool:
        try:
            from alpaca.trading.client import TradingClient

            self._client = TradingClient(
                self._api_key, self._secret_key, paper=(self._mode == TradingMode.PAPER)
            )
            logger.info("Alpaca connected (mode=%s)", self._mode)
            return True
        except ImportError:
            logger.error(
                "alpaca-py not installed. pip install emerald-exchange[alpaca]"
            )
            return False

    def disconnect(self) -> None:
        self._client = None

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
    ) -> ExecutionResult:
        if not self._client:
            return ExecutionResult(
                order_id="",
                status=OrderStatus.REJECTED,
                filled_qty=0,
                average_price=0,
                fees=0,
                exchange="alpaca",
            )
        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide as AlpSide, TimeInForce

            alp_side = AlpSide.BUY if side == OrderSide.BUY else AlpSide.SELL
            if order_type == OrderType.LIMIT and limit_price:
                req = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=alp_side,
                    limit_price=limit_price,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                req = MarketOrderRequest(
                    symbol=symbol, qty=qty, side=alp_side, time_in_force=TimeInForce.DAY
                )
            order = self._client.submit_order(req)
            return ExecutionResult(
                order_id=str(order.id),
                status=OrderStatus.SUBMITTED,
                filled_qty=float(order.filled_qty or 0),
                average_price=float(order.filled_avg_price or 0),
                fees=0.0,
                exchange="alpaca",
                raw={"alpaca_order_id": str(order.id)},
            )
        except Exception as e:
            logger.error("Alpaca order failed: error_type=%s", type(e).__name__)
            return ExecutionResult(
                order_id="",
                status=OrderStatus.REJECTED,
                filled_qty=0,
                average_price=0,
                fees=0,
                exchange="alpaca",
                raw={"error": "Operation failed"},
            )

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    def get_order_status(self, order_id: str) -> ExecutionResult:
        try:
            order = self._client.get_order_by_id(order_id)
            status_map = {
                "filled": OrderStatus.FILLED,
                "cancelled": OrderStatus.CANCELLED,
                "new": OrderStatus.SUBMITTED,
                "partially_filled": OrderStatus.PARTIAL,
            }
            return ExecutionResult(
                order_id=str(order.id),
                status=status_map.get(str(order.status), OrderStatus.PENDING),
                filled_qty=float(order.filled_qty or 0),
                average_price=float(order.filled_avg_price or 0),
                fees=0.0,
                exchange="alpaca",
            )
        except Exception:
            return ExecutionResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                filled_qty=0,
                average_price=0,
                fees=0,
                exchange="alpaca",
            )

    def get_positions(self) -> list[Position]:
        try:
            positions = self._client.get_all_positions()
            return [
                Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                    unrealized_pnl=float(p.unrealized_pl),
                    side="long" if float(p.qty) > 0 else "short",
                    exchange="alpaca",
                )
                for p in positions
            ]
        except Exception:
            return []

    def get_account(self) -> AccountInfo:
        try:
            acct = self._client.get_account()
            return AccountInfo(
                equity=float(acct.equity),
                cash=float(acct.cash),
                buying_power=float(acct.buying_power),
                exchange="alpaca",
            )
        except Exception:
            return AccountInfo(equity=0, cash=0, buying_power=0, exchange="alpaca")

    def get_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, bid=0, ask=0, last=0, volume=0)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        return []


def _validate_ccxt_interval(interval: str, exchange: Any, exchange_id: str) -> None:
    """Raise :class:`UnsupportedIntervalError` rather than silently degrade.

    Checked against this module's own ccxt timeframe table, and — when the
    connected exchange publishes one — the exchange's own narrower
    ``.timeframes`` set, so a request for an interval the exchange itself
    does not offer is caught before wasting a round trip.
    """
    if interval not in _INTERVAL_MS:
        raise UnsupportedIntervalError(
            f"interval {interval!r} is not a supported ccxt timeframe "
            f"(supported: {', '.join(CCXT_TIMEFRAMES)})"
        )
    exchange_timeframes = getattr(exchange, "timeframes", None) or {}
    if exchange_timeframes and interval not in exchange_timeframes:
        raise UnsupportedIntervalError(
            f"exchange {exchange_id!r} does not support interval {interval!r} "
            f"(it supports: {', '.join(sorted(exchange_timeframes))})"
        )


def _fetch_ccxt_ohlcv_page(
    exchange: Any,
    symbol: str,
    interval: str,
    exchange_id: str,
    since_ms: int,
    page_limit: int,
) -> list[list[float]]:
    """One paced ``fetch_ohlcv`` call, wrapped so any failure fails loud."""
    try:
        return exchange.fetch_ohlcv(symbol, interval, since=since_ms, limit=page_limit)
    except Exception as exc:
        raise HistoricalDataError(
            f"fetch_ohlcv failed for {symbol!r} on {exchange_id!r}: {type(exc).__name__}"
        ) from exc


def _fetch_ccxt_ohlcv_pages(
    exchange: Any,
    symbol: str,
    interval: str,
    exchange_id: str,
    floor_ms: int,
    now_ms: int,
    page_limit: int = 1000,
) -> list[list[float]]:
    """Walk ``since`` forward one ccxt page at a time to cover ``[floor_ms, now_ms)``.

    Stops on a short page (end of available history), on zero forward
    progress, or once ``now_ms`` is reached; raises :class:`HistoricalDataError`
    if :data:`MAX_HISTORICAL_PAGES` is exceeded rather than returning a
    quietly truncated result.
    """
    interval_ms = _INTERVAL_MS[interval]
    since_ms = floor_ms
    candles: list[list[float]] = []
    for pages in range(MAX_HISTORICAL_PAGES + 1):
        if since_ms >= now_ms:
            return candles
        if pages == MAX_HISTORICAL_PAGES:
            raise HistoricalDataError(
                f"get_historical({symbol!r}, interval={interval!r}) exceeded "
                f"{MAX_HISTORICAL_PAGES} pages without covering the requested "
                "period — narrow the period or widen the interval"
            )
        page = _fetch_ccxt_ohlcv_page(
            exchange, symbol, interval, exchange_id, since_ms, page_limit
        )
        if not page:
            return candles
        candles.extend(page)
        next_since = int(page[-1][0]) + interval_ms
        if next_since <= since_ms or len(page) < page_limit:
            return candles
        since_ms = next_since
    return candles  # pragma: no cover — loop always returns via one of the above


def _dedupe_and_clip(candles: list[list[float]], floor_ms: int) -> list[list[float]]:
    """Drop timestamp duplicates from overlapping pages; clip to the lookback floor."""
    seen: set[float] = set()
    deduped = []
    for c in candles:
        if c[0] not in seen and c[0] >= floor_ms:
            seen.add(c[0])
            deduped.append(c)
    return deduped


def _candles_to_ohlcv(candles: list[list[float]]) -> list[OHLCV]:
    """Project raw ``[ts, o, h, l, c, v]`` ccxt rows onto :class:`OHLCV`."""
    return [
        OHLCV(
            timestamp=datetime.fromtimestamp(c[0] / 1000, tz=UTC).isoformat(),
            open=c[1],
            high=c[2],
            low=c[3],
            close=c[4],
            volume=c[5],
        )
        for c in candles
    ]


class CCXTBackend:
    """CCXT unified crypto exchange backend — CONCEPT:EX-AHE.harness.ee-4.
    Supports 100+ exchanges: Binance, Coinbase, Kraken, etc.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: str = "",
        secret: str = "",
        mode: TradingMode = TradingMode.PAPER,
    ):
        self._exchange_id = exchange_id
        self._api_key = api_key
        self._secret = secret
        self._mode = mode
        self._exchange: Any = None

    @property
    def name(self) -> str:
        return f"ccxt:{self._exchange_id}"

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def supported_assets(self) -> list[str]:
        return ["crypto"]

    def connect(self) -> bool:
        try:
            import ccxt

            exchange_class = getattr(ccxt, self._exchange_id)
            config: dict[str, Any] = {"apiKey": self._api_key, "secret": self._secret}
            if self._mode == TradingMode.PAPER:
                config["sandbox"] = True
            self._exchange = exchange_class(config)
            self._exchange.load_markets()
            logger.info("CCXT %s connected (mode=%s)", self._exchange_id, self._mode)
            return True
        except ImportError:
            logger.error("ccxt not installed. pip install emerald-exchange[crypto]")
            return False

    def disconnect(self) -> None:
        self._exchange = None

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
    ) -> ExecutionResult:
        if not self._exchange:
            return ExecutionResult(
                order_id="",
                status=OrderStatus.REJECTED,
                filled_qty=0,
                average_price=0,
                fees=0,
                exchange=self._exchange_id,
            )
        try:
            ot = "limit" if order_type == OrderType.LIMIT else "market"
            order = self._exchange.create_order(
                symbol, ot, side.value, qty, limit_price
            )
            return ExecutionResult(
                order_id=order["id"],
                status=OrderStatus.SUBMITTED,
                filled_qty=float(order.get("filled", 0)),
                average_price=float(order.get("average", 0) or 0),
                fees=float(order.get("fee", {}).get("cost", 0) or 0),
                exchange=self._exchange_id,
                raw=order,
            )
        except Exception as e:
            logger.error("CCXT order failed: error_type=%s", type(e).__name__)
            return ExecutionResult(
                order_id="",
                status=OrderStatus.REJECTED,
                filled_qty=0,
                average_price=0,
                fees=0,
                exchange=self._exchange_id,
                raw={"error": "Operation failed"},
            )

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._exchange.cancel_order(order_id)
            return True
        except Exception:
            return False

    def get_order_status(self, order_id: str) -> ExecutionResult:
        try:
            order = self._exchange.fetch_order(order_id)
            status_map = {
                "closed": OrderStatus.FILLED,
                "canceled": OrderStatus.CANCELLED,
                "open": OrderStatus.SUBMITTED,
            }
            return ExecutionResult(
                order_id=order["id"],
                status=status_map.get(order["status"], OrderStatus.PENDING),
                filled_qty=float(order.get("filled", 0)),
                average_price=float(order.get("average", 0) or 0),
                fees=0.0,
                exchange=self._exchange_id,
            )
        except Exception:
            return ExecutionResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                filled_qty=0,
                average_price=0,
                fees=0,
                exchange=self._exchange_id,
            )

    def get_positions(self) -> list[Position]:
        try:
            balances = self._exchange.fetch_balance()
            positions = []
            for asset, info in balances.get("total", {}).items():
                if float(info) > 0 and asset != "USD":
                    positions.append(
                        Position(
                            symbol=asset,
                            qty=float(info),
                            avg_entry_price=0,
                            current_price=0,
                            unrealized_pnl=0,
                            side="long",
                            exchange=self._exchange_id,
                        )
                    )
            return positions
        except Exception:
            return []

    def get_account(self) -> AccountInfo:
        try:
            balance = self._exchange.fetch_balance()
            total = balance.get("total", {})
            usd = float(total.get("USD", 0) or total.get("USDT", 0) or 0)
            return AccountInfo(
                equity=usd,
                cash=usd,
                buying_power=usd,
                exchange=self._exchange_id,
                currency="USD",
            )
        except Exception:
            return AccountInfo(
                equity=0, cash=0, buying_power=0, exchange=self._exchange_id
            )

    def get_quote(self, symbol: str) -> Quote:
        try:
            ticker = self._exchange.fetch_ticker(symbol)
            return Quote(
                symbol=symbol,
                bid=float(ticker.get("bid", 0) or 0),
                ask=float(ticker.get("ask", 0) or 0),
                last=float(ticker.get("last", 0) or 0),
                volume=float(ticker.get("baseVolume", 0) or 0),
            )
        except Exception:
            return Quote(symbol=symbol, bid=0, ask=0, last=0, volume=0)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        """Fetch OHLCV bars for ``period`` at exactly ``interval``, paginated.

        Fails loud instead of silently degrading: an unsupported ``interval``
        raises :class:`UnsupportedIntervalError` rather than being remapped to
        daily bars, and a connection/exchange failure raises
        :class:`HistoricalDataError` rather than returning ``[]`` (an asset
        that legitimately has no history still returns ``[]``, from a call
        that actually succeeded). See :func:`_validate_ccxt_interval` and
        :func:`_fetch_ccxt_ohlcv_pages` for the pagination mechanics.
        """
        _validate_ccxt_interval(interval, self._exchange, self._exchange_id)
        if not self._exchange:
            raise HistoricalDataError(
                f"CCXT backend {self._exchange_id!r} is not connected; call connect() first"
            )
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        floor_ms = now_ms - _period_to_lookback_ms(period)
        candles = _fetch_ccxt_ohlcv_pages(
            self._exchange, symbol, interval, self._exchange_id, floor_ms, now_ms
        )
        return _candles_to_ohlcv(_dedupe_and_clip(candles, floor_ms))


class FreqtradeBackend:
    """Freqtrade REST API backend — CONCEPT:EX-AHE.harness.ee-5."""

    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        api_key: str = "",
        mode: TradingMode = TradingMode.PAPER,
    ):
        self._api_url = api_url
        self._api_key = api_key
        self._mode = mode

    @property
    def name(self) -> str:
        return "freqtrade"

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def supported_assets(self) -> list[str]:
        return ["crypto"]

    def connect(self) -> bool:
        logger.info("Freqtrade backend stub — implement REST API calls")
        return True

    def disconnect(self) -> None:
        logger.info("Freqtrade backend disconnected")

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
    ) -> ExecutionResult:
        logger.warning("Freqtrade backend: order routing via freqtrade strategies")
        return ExecutionResult(
            order_id="FT-STUB",
            status=OrderStatus.PENDING,
            filled_qty=0,
            average_price=0,
            fees=0,
            exchange="freqtrade",
        )

    def cancel_order(self, order_id: str) -> bool:
        return False

    def get_order_status(self, order_id: str) -> ExecutionResult:
        return ExecutionResult(
            order_id=order_id,
            status=OrderStatus.PENDING,
            filled_qty=0,
            average_price=0,
            fees=0,
            exchange="freqtrade",
        )

    def get_positions(self) -> list[Position]:
        return []

    def get_account(self) -> AccountInfo:
        return AccountInfo(equity=0, cash=0, buying_power=0, exchange="freqtrade")

    def get_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, bid=0, ask=0, last=0, volume=0)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        return []


class PolymarketBackend:
    """Polymarket CLOB v2 REST/WebSocket Backend integration."""

    def __init__(
        self,
        private_key: str = "",
        host: str = "https://clob.polymarket.com",
        chain_id: int = 137,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
        mode: TradingMode = TradingMode.PAPER,
    ):
        self._private_key = private_key
        self._host = host
        self._chain_id = chain_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._api_passphrase = api_passphrase
        self._mode = mode
        self._client = None

    @property
    def name(self) -> str:
        return "polymarket"

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def supported_assets(self) -> list[str]:
        return ["crypto", "predictions"]

    def connect(self) -> bool:
        if self._mode == TradingMode.PAPER:
            logger.info("Polymarket backend initialized in paper simulation mode")
            return True

        try:
            from py_clob_client_v2 import ApiCreds, ClobClient

            if self._api_key and self._api_secret and self._api_passphrase:
                creds = ApiCreds(
                    api_key=self._api_key,
                    api_secret=self._api_secret,
                    api_passphrase=self._api_passphrase,
                )
                self._client = ClobClient(
                    host=self._host,
                    chain_id=self._chain_id,
                    key=self._private_key,
                    creds=creds,
                )
            else:
                self._client = ClobClient(
                    host=self._host,
                    chain_id=self._chain_id,
                    key=self._private_key,
                )
                # Auto-derive credentials if not supplied
                creds = self._client.create_or_derive_api_key()
                # Re-init client with derived creds
                self._client = ClobClient(
                    host=self._host,
                    chain_id=self._chain_id,
                    key=self._private_key,
                    creds=creds,
                )
            logger.info("Successfully connected to Polymarket CLOB v2 API")
            return True
        except ImportError:
            logger.error(
                "py_clob_client_v2 not installed. Run 'pip install py_clob_client_v2'"
            )
            if self._mode == TradingMode.LIVE:
                raise RuntimeError(
                    "py_clob_client_v2 is required for Live Polymarket trading"
                )
            return True
        except Exception as e:
            logger.error("Operation failed: error_type=%s", type(e).__name__)
            if self._mode == TradingMode.LIVE:
                raise
            return False

    def disconnect(self) -> None:
        self._client = None

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: float | None = None,
    ) -> ExecutionResult:
        if self._mode == TradingMode.PAPER or not self._client:
            # Paper execution fallback
            price = limit_price if limit_price and limit_price > 0 else 0.50
            return ExecutionResult(
                order_id="PM-PAPER-ORDER",
                status=OrderStatus.FILLED,
                filled_qty=qty,
                average_price=price,
                fees=0.0,
                exchange="polymarket",
            )

        try:
            from py_clob_client_v2 import (
                OrderArgs,
                PartialCreateOrderOptions,
                Side,
                OrderType as PMOrderType,
            )
            from py_clob_client_v2 import (
                MarketOrderArgs,
                OrderType as PMMarketOrderType,
            )

            pm_side = Side.BUY if side == OrderSide.BUY else Side.SELL

            if order_type == OrderType.MARKET:
                resp = self._client.create_and_post_market_order(
                    order_args=MarketOrderArgs(
                        token_id=symbol,
                        amount=qty,  # In Polymarket market order, amount is typically in USDC
                        side=pm_side,
                        order_type=PMMarketOrderType.FOK,
                    ),
                    options=PartialCreateOrderOptions(tick_size="0.01"),
                    order_type=PMMarketOrderType.FOK,
                )
                status = OrderStatus.FILLED
                order_id = resp.get("orderID", "PM-MKT-ORDER")
            else:
                price = limit_price if limit_price else 0.50
                resp = self._client.create_and_post_order(
                    order_args=OrderArgs(
                        token_id=symbol,
                        price=price,
                        side=pm_side,
                        size=qty,
                    ),
                    options=PartialCreateOrderOptions(tick_size="0.01"),
                    order_type=PMOrderType.GTC,
                )
                status = OrderStatus.SUBMITTED
                order_id = resp.get("orderID", "PM-LMT-ORDER")

            return ExecutionResult(
                order_id=order_id,
                status=status,
                filled_qty=qty if status == OrderStatus.FILLED else 0.0,
                average_price=limit_price if limit_price else 0.50,
                fees=0.0,
                exchange="polymarket",
                raw=resp if isinstance(resp, dict) else {"response": str(resp)},
            )
        except Exception as e:
            logger.error("Polymarket order failed: error_type=%s", type(e).__name__)
            return ExecutionResult(
                order_id="",
                status=OrderStatus.REJECTED,
                filled_qty=0.0,
                average_price=0.0,
                fees=0.0,
                exchange="polymarket",
                raw={"error": "Operation failed"},
            )

    def cancel_order(self, order_id: str) -> bool:
        if self._mode == TradingMode.PAPER or not self._client:
            return True
        try:
            self._client.cancel_order(order_id)
            return True
        except Exception as e:
            logger.error("Operation failed: error_type=%s", type(e).__name__)
            return False

    def get_order_status(self, order_id: str) -> ExecutionResult:
        if self._mode == TradingMode.PAPER or not self._client:
            return ExecutionResult(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_qty=1.0,
                average_price=0.5,
                fees=0.0,
                exchange="polymarket",
            )
        try:
            order = self._client.get_order(order_id)
            # Map statuses
            status_map = {
                "closed": OrderStatus.FILLED,
                "canceled": OrderStatus.CANCELLED,
                "open": OrderStatus.SUBMITTED,
                "partially_filled": OrderStatus.PARTIAL,
            }
            raw_status = order.get("status", "open")
            return ExecutionResult(
                order_id=order.get("id", order_id),
                status=status_map.get(raw_status.lower(), OrderStatus.PENDING),
                filled_qty=float(order.get("filled", 0.0)),
                average_price=float(order.get("price", 0.5)),
                fees=0.0,
                exchange="polymarket",
                raw=order,
            )
        except Exception as e:
            logger.error(
                "Failed to fetch order status: error_type=%s", type(e).__name__
            )
            return ExecutionResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                filled_qty=0.0,
                average_price=0.0,
                fees=0.0,
                exchange="polymarket",
            )

    def get_positions(self) -> list[Position]:
        if self._mode == TradingMode.PAPER or not self._client:
            return [
                Position(
                    symbol="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC
                    qty=1000.0,
                    avg_entry_price=1.0,
                    current_price=1.0,
                    unrealized_pnl=0.0,
                    side="long",
                    exchange="polymarket",
                )
            ]
        try:
            positions = []
            assets = self._client.get_positions()
            for asset in assets:
                qty = float(asset.get("size", 0.0))
                if qty > 0:
                    positions.append(
                        Position(
                            symbol=asset.get("asset_id", ""),
                            qty=qty,
                            avg_entry_price=float(asset.get("avg_price", 0.0)),
                            current_price=float(asset.get("current_price", 0.0)),
                            unrealized_pnl=float(asset.get("unrealized_pnl", 0.0)),
                            side="long",
                            exchange="polymarket",
                        )
                    )
            return positions
        except Exception as e:
            logger.error("Operation failed: error_type=%s", type(e).__name__)
            return []

    def get_account(self) -> AccountInfo:
        if self._mode == TradingMode.PAPER or not self._client:
            return AccountInfo(
                equity=1000.0, cash=1000.0, buying_power=1000.0, exchange="polymarket"
            )
        try:
            balance_info = self._client.get_balance()
            cash = float(balance_info.get("balance", 0.0))
            return AccountInfo(
                equity=cash,
                cash=cash,
                buying_power=cash,
                exchange="polymarket",
                currency="USDC",
            )
        except Exception as e:
            logger.error("Operation failed: error_type=%s", type(e).__name__)
            return AccountInfo(
                equity=0.0, cash=0.0, buying_power=0.0, exchange="polymarket"
            )

    def get_quote(self, symbol: str) -> Quote:
        if self._mode == TradingMode.PAPER or not self._client:
            return Quote(symbol=symbol, bid=0.49, ask=0.51, last=0.50, volume=10000.0)
        try:
            book = self._client.get_orderbook(symbol)
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            bid = float(bids[0].get("price", 0.0)) if bids else 0.0
            ask = float(asks[0].get("price", 0.0)) if asks else 0.0
            return Quote(
                symbol=symbol,
                bid=bid,
                ask=ask,
                last=(bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.50,
                volume=0.0,
            )
        except Exception as e:
            logger.error(
                "Failed to fetch Polymarket quote: error_type=%s", type(e).__name__
            )
            return Quote(symbol=symbol, bid=0.0, ask=0.0, last=0.0, volume=0.0)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        return []

    def merge_positions(self, market_id: str) -> bool:
        """Call Polymarket client to merge YES/NO positions."""
        if self._mode == TradingMode.PAPER or not self._client:
            logger.info("Simulated position merge for market %s", market_id)
            return True
        try:
            self._client.merge_positions(market_id)
            logger.info("Successfully merged YES/NO positions for market %s", market_id)
            return True
        except Exception as e:
            logger.error("Operation failed: error_type=%s", type(e).__name__)
            return False


# --- Exchange Registry ---

BACKEND_REGISTRY: dict[str, type] = {
    "paper": PaperBackend,
    "alpaca": AlpacaBackend,
    "ccxt": CCXTBackend,
    "binance": CCXTBackend,
    "coinbase": CCXTBackend,
    "kraken": CCXTBackend,
    "freqtrade": FreqtradeBackend,
    "polymarket": PolymarketBackend,
}


def create_backend(
    name: str,
    config: dict[str, Any] | None = None,
    mode: TradingMode = TradingMode.PAPER,
) -> ExchangeBackend:
    """Factory to create exchange backends from config. CONCEPT:EX-AHE.harness.ee."""
    config = config or {}
    backend_class = BACKEND_REGISTRY.get(name)
    if not backend_class:
        logger.warning("Unknown backend '%s', falling back to paper", name)
        return PaperBackend()

    if name in ("binance", "coinbase", "kraken"):
        return CCXTBackend(exchange_id=name, mode=mode, **config)

    if name == "paper":
        return PaperBackend(**config)  # Paper mode is always PAPER

    return backend_class(mode=mode, **config)  # type: ignore[call-arg]
