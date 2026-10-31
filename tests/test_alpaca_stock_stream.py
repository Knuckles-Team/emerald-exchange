"""Exercise live provider callback registration and bus delivery."""

import asyncio

import pytest
from msgpack import Timestamp
from scion_sdk.streaming import CallbackSubscriber, StreamBus

from emerald_exchange.alpaca_stock_stream import AlpacaStockStream
from tests.test_alpaca_stock_bars import BAR, QUOTE


class Provider:
    def subscribe_quotes(self, callback, *symbols):
        self.quotes, self.symbols = callback, symbols

    def subscribe_bars(self, callback, *symbols):
        self.bars = callback

    def subscribe_updated_bars(self, callback, *symbols):
        self.updated = callback

    def run(self):
        self.running = True

    def stop(self):
        self.running = False


def test_real_provider_client_and_feed_are_composed():
    stream = AlpacaStockStream.connect(
        "key", "secret", StreamBus(), ("AAPL",), feed="iex", license_tag="licensed"
    )
    assert stream.client._handlers["quotes"]["AAPL"] == stream.on_quote
    assert stream.client._handlers["bars"]["AAPL"] == stream.on_bar
    assert stream.client._handlers["updatedBars"]["AAPL"] == stream.on_updated_bar


def test_quotes_and_revised_bars_preserve_source_time_and_identity():
    async def exercise():
        bus, provider, received = StreamBus(), Provider(), []
        bus.subscribe("*", CallbackSubscriber(on_message_fn=received.append))
        stream = AlpacaStockStream(
            provider, bus, ("AAPL",), feed="iex", license_tag="licensed"
        )
        stream.run()
        assert provider.running
        await provider.quotes(
            {**QUOTE, "T": "q", "S": "AAPL", "t": Timestamp(1767364200, 123456789)}
        )
        await provider.bars({**BAR, "T": "b", "S": "AAPL"})
        await provider.updated({**BAR, "T": "u", "S": "AAPL", "c": 101})
        stream.stop()
        assert not provider.running
        quote, first, updated = received
        assert quote.topic == "market.AAPL.quotes"
        assert quote.timestamp == "2026-01-02T14:30:00.123456789Z"
        assert "last" not in quote.data
        assert first.data["bar_id"] == updated.data["bar_id"]
        assert first.data["updated"] is False and updated.data["updated"] is True
        assert updated.data["close"] == 101
        assert first.data["adjustment"] == "raw"
        assert first.data["session_scope"] == "feed_native"

    asyncio.run(exercise())


def test_invalid_events_refuse_before_publication():
    async def exercise():
        bus, provider, received = StreamBus(), Provider(), []
        bus.subscribe("*", CallbackSubscriber(on_message_fn=received.append))
        AlpacaStockStream(provider, bus, ("AAPL",), feed="iex", license_tag="licensed")
        with pytest.raises(ValueError):
            await provider.bars({**BAR, "T": "b", "S": "OTHER"})
        with pytest.raises(ValueError):
            await provider.updated({**BAR, "T": "b", "S": "AAPL"})
        assert not received

    asyncio.run(exercise())


def test_provider_websocket_auth_subscribe_and_delivery():
    import msgpack
    import websockets
    from alpaca.data.enums import DataFeed
    from alpaca.data.live.stock import StockDataStream

    async def exercise():
        received, ready = [], asyncio.Event()

        async def handler(socket):
            await socket.send(msgpack.packb([{"T": "success", "msg": "connected"}]))
            auth = msgpack.unpackb(await socket.recv())
            assert auth == {
                "action": "auth",
                "key": "test-key",
                "secret": "test-secret",
            }
            await socket.send(msgpack.packb([{"T": "success", "msg": "authenticated"}]))
            subscription = msgpack.unpackb(await socket.recv())
            assert subscription["quotes"] == ["AAPL"]
            assert subscription["bars"] == ["AAPL"]
            assert subscription["updatedBars"] == ["AAPL"]
            await socket.send(
                msgpack.packb(
                    [
                        {
                            **QUOTE,
                            "T": "q",
                            "S": "AAPL",
                            "t": Timestamp(1767364200, 123456789),
                        }
                    ]
                )
            )
            await ready.wait()

        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            client = StockDataStream(
                "test-key",
                "test-secret",
                raw_data=True,
                feed=DataFeed.IEX,
                url_override=f"ws://127.0.0.1:{port}",
            )
            bus = StreamBus()

            async def receive(message):
                received.append(message)
                ready.set()

            bus.subscribe("*", CallbackSubscriber(on_message_fn=receive))
            stream = AlpacaStockStream(
                client, bus, ("AAPL",), feed="iex", license_tag="licensed"
            )
            running = asyncio.create_task(asyncio.to_thread(stream.run))
            try:
                await asyncio.wait_for(ready.wait(), timeout=5)
                assert received[0].timestamp == "2026-01-02T14:30:00.123456789Z"
                assert received[0].source == "alpaca"
            finally:
                await asyncio.to_thread(stream.stop)
                await asyncio.wait_for(running, timeout=10)

    asyncio.run(exercise())
