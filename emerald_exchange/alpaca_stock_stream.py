"""Live Alpaca quotes and minute bars on the SDK's in-process stream bus.

The provider stream is live-only: reconnects can miss data. Consumers requiring
complete history must reconcile with the bounded historical API. Updated bars
are published on the same bar topic with the provider's revision marker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from msgpack import Timestamp
from scion_sdk.streaming import StreamBus, StreamMessage

from emerald_exchange.alpaca_stock_history import (
    _SYMBOL,
    _bar,
    _instant,
    read_stock_quote,
)


class _QuoteResponse:
    def __init__(self, symbol: str, raw: dict[str, Any]) -> None:
        self.symbol, self.raw = symbol, raw

    def get(self, _path: str, *, data: dict[str, Any]) -> dict[str, Any]:
        return {"quotes": {self.symbol: self.raw}}


def _wire_timestamp(raw: dict[str, Any]) -> dict[str, Any]:
    timestamp = raw.get("t")
    if isinstance(timestamp, Timestamp):
        try:
            seconds = datetime.fromtimestamp(timestamp.seconds, UTC)
        except (OverflowError, OSError, ValueError):
            raise ValueError("invalid stock stream timestamp") from None
        raw = {
            **raw,
            "t": seconds.strftime("%Y-%m-%dT%H:%M:%S")
            + f".{timestamp.nanoseconds:09d}Z",
        }
    return raw


class AlpacaStockStream:
    """Compose Alpaca's authenticated websocket client with the SDK bus.

    ``run`` blocks until stopped and must run outside an existing event loop.
    On disconnect the provider client reconnects, without backfilling gaps.
    """

    def __init__(
        self,
        client: Any,
        bus: StreamBus,
        symbols: tuple[str, ...],
        *,
        feed: str,
        license_tag: str,
    ) -> None:
        if (
            not symbols
            or len(symbols) > 30
            or len(set(symbols)) != len(symbols)
            or any(not isinstance(s, str) or not _SYMBOL.fullmatch(s) for s in symbols)
        ):
            raise ValueError("stream requires one to thirty distinct stock symbols")
        if feed not in {"iex", "sip"}:
            raise ValueError("stock streaming requires iex or sip")
        if not isinstance(license_tag, str) or not license_tag.strip():
            raise ValueError("stock streaming requires a license tag")
        self.client, self.bus, self.symbols = client, bus, frozenset(symbols)
        self.feed, self.license_tag = feed, license_tag
        client.subscribe_quotes(self.on_quote, *symbols)
        client.subscribe_bars(self.on_bar, *symbols)
        client.subscribe_updated_bars(self.on_updated_bar, *symbols)

    @classmethod
    def connect(
        cls,
        api_key: str,
        secret_key: str,
        bus: StreamBus,
        symbols: tuple[str, ...],
        *,
        feed: str,
        license_tag: str,
    ) -> AlpacaStockStream:
        """Create the real provider websocket; credentials stay in its client."""
        from alpaca.data.enums import DataFeed
        from alpaca.data.live.stock import StockDataStream

        if feed not in {"iex", "sip"}:
            raise ValueError("stock streaming requires iex or sip")
        client = StockDataStream(
            api_key, secret_key, raw_data=True, feed=DataFeed(feed)
        )
        return cls(client, bus, symbols, feed=feed, license_tag=license_tag)

    def run(self) -> None:
        self.client.run()

    def stop(self) -> None:
        self.client.stop()

    def _symbol(self, raw: Any, kind: str) -> str:
        if (
            not isinstance(raw, dict)
            or raw.get("T") != kind
            or raw.get("S") not in self.symbols
        ):
            raise ValueError("invalid stock stream event")
        return raw["S"]

    async def on_quote(self, raw: Any) -> None:
        symbol = self._symbol(raw, "q")
        raw = _wire_timestamp(raw)
        quote = read_stock_quote(
            _QuoteResponse(symbol, raw),
            symbol=symbol,
            feed=self.feed,
            license_tag=self.license_tag,
        )["quotes"][0]
        await self.bus.publish(
            StreamMessage(
                topic=f"market.{symbol}.quotes",
                data=quote,
                timestamp=quote["timestamp"],
                source="alpaca",
            )
        )

    async def _publish_bar(self, raw: Any, kind: str) -> None:
        symbol = self._symbol(raw, kind)
        raw = _wire_timestamp(raw)
        _, instant = _instant(raw.get("t"))
        bar = _bar(
            raw,
            symbol=symbol,
            timeframe="1Min",
            adjustment="raw",
            feed=self.feed,
            license_tag=self.license_tag,
            start=instant,
            end=instant,
        )
        bar["updated"] = kind == "u"
        await self.bus.publish(
            StreamMessage(
                topic=f"market.{symbol}.bars",
                data=bar,
                timestamp=bar["timestamp"],
                source="alpaca",
            )
        )

    async def on_bar(self, raw: Any) -> None:
        await self._publish_bar(raw, "b")

    async def on_updated_bar(self, raw: Any) -> None:
        await self._publish_bar(raw, "u")
