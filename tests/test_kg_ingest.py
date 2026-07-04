"""Native epistemic-graph typed-node ingestion — Wire-First coverage.

Exercises the real ``ingest_entities`` + record mappers + ``ingest_backend_snapshot`` seam
with a fake engine client and a fake exchange backend (no engine, no exchange required),
asserting the txn add_node/commit + edge calls and the trading-record → typed-node mapping.
CONCEPT:AU-KG.ingest.enterprise-source-extractor.
"""

from __future__ import annotations

from emerald_exchange.backends import AccountInfo, OHLCV, Position, Quote
from emerald_exchange.kg_ingest import (
    ingest_backend_snapshot,
    ingest_entities,
    map_account,
    map_bars,
    map_positions,
    map_quote,
    map_trade,
)


class _FakeTxn:
    def __init__(self):
        self.nodes = {}
        self.committed = False

    def begin(self, graph=None):
        self.graph = graph
        return "txn-1"

    def add_node(self, txn, node_id, props):
        self.nodes[node_id] = props

    def commit(self, txn):
        self.committed = True
        return True


class _FakeEdges:
    def __init__(self):
        self.edges = []

    def add(self, src, dst, props):
        self.edges.append((src, dst, props))


class _FakeClient:
    def __init__(self):
        self.txn = _FakeTxn()
        self.edges = _FakeEdges()


class _FakeBackend:
    """Minimal ExchangeBackend stand-in returning fixed records."""

    name = "paper"
    mode = "paper"

    def get_account(self):
        return AccountInfo(
            equity=100000.0,
            cash=50000.0,
            buying_power=200000.0,
            margin_used=0.0,
            currency="USD",
            exchange="paper",
        )

    def get_positions(self):
        return [
            Position(
                symbol="AAPL",
                qty=10,
                avg_entry_price=150.0,
                current_price=160.0,
                unrealized_pnl=100.0,
                side="long",
                exchange="paper",
            )
        ]

    def get_quote(self, symbol):
        return Quote(symbol=symbol, bid=159.9, ask=160.1, last=160.0, volume=1_000_000)

    def get_historical(self, symbol, period="1y", interval="1d"):
        return [
            OHLCV(
                timestamp="2026-07-01T00:00:00Z",
                open=155.0,
                high=161.0,
                low=154.0,
                close=160.0,
                volume=2_000_000,
            )
        ]


# --------------------------------------------------------------------------- #
# core write path
# --------------------------------------------------------------------------- #
def test_ingest_entities_writes_nodes_and_edges():
    c = _FakeClient()
    res = ingest_entities(
        [
            {"id": "emerald:instrument:AAPL", "type": "Instrument", "name": "AAPL"},
            {"id": "emerald:portfolio:paper", "type": "Portfolio"},
        ],
        [
            {
                "source": "emerald:portfolio:paper",
                "target": "emerald:instrument:AAPL",
                "type": "holdsPosition",
            }
        ],
        client=c,
        graph="__commons__",
    )
    assert res == {"nodes": 2, "edges": 1}
    assert c.txn.committed is True
    assert set(c.txn.nodes) == {"emerald:instrument:AAPL", "emerald:portfolio:paper"}
    # provenance stamped
    assert c.txn.nodes["emerald:instrument:AAPL"]["source"] == "emerald-exchange"
    assert c.txn.nodes["emerald:instrument:AAPL"]["domain"] == "emerald"
    assert c.edges.edges[0][2] == {"type": "holdsPosition"}


def test_ingest_noops_without_engine():
    # No injected client + no reachable engine -> clean no-op.
    assert ingest_entities([{"id": "x", "type": "Instrument"}]) is None


def test_ingest_empty_is_noop():
    assert ingest_entities([], client=_FakeClient()) is None


# --------------------------------------------------------------------------- #
# mappers
# --------------------------------------------------------------------------- #
def test_map_account_to_portfolio():
    e, r = map_account(
        {
            "equity": 100000.0,
            "cash": 50000.0,
            "buying_power": 200000.0,
            "margin_used": 0.0,
            "currency": "USD",
            "exchange": "paper",
        }
    )
    assert r == []
    node = e[0]
    assert node["id"] == "emerald:portfolio:paper"
    assert node["type"] == "Portfolio"
    assert node["equity"] == 100000.0
    assert node["buyingPower"] == 200000.0


def test_map_positions_links_instrument_and_portfolio():
    e, r = map_positions(
        [
            {
                "symbol": "AAPL",
                "qty": 10,
                "avg_entry_price": 150.0,
                "current_price": 160.0,
                "unrealized_pnl": 100.0,
                "side": "long",
                "exchange": "paper",
            }
        ]
    )
    ids = {n["id"]: n for n in e}
    assert "emerald:position:paper:AAPL" in ids
    assert "emerald:instrument:AAPL" in ids
    assert ids["emerald:position:paper:AAPL"]["type"] == "Position"
    assert ids["emerald:instrument:AAPL"]["type"] == "Instrument"
    rel_types = {rel["type"] for rel in r}
    assert rel_types == {"ofInstrument", "holdsPosition"}


def test_map_quote_and_bars_and_trade():
    qe, qr = map_quote(
        {
            "symbol": "BTC",
            "bid": 1.0,
            "ask": 2.0,
            "last": 1.5,
            "volume": 9,
            "timestamp": "",
        }
    )
    assert any(n["type"] == "Quote" for n in qe)
    assert qr[0]["type"] == "ofInstrument"

    be, br = map_bars(
        "BTC",
        [
            {
                "timestamp": "2026-07-01T00:00:00Z",
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 3,
            }
        ],
    )
    bar = next(n for n in be if n["type"] == "MarketBar")
    assert bar["id"] == "emerald:bar:BTC:2026-07-01T00:00:00Z"
    assert bar["close"] == 1.5
    assert br[0]["type"] == "ofInstrument"

    te, tr = map_trade(
        {
            "order_id": "PAPER-000001",
            "status": "filled",
            "filled_qty": 5,
            "average_price": 100.0,
            "fees": 0.5,
            "exchange": "paper",
            "symbol": "AAPL",
        }
    )
    trade = next(n for n in te if n["type"] == "Trade")
    assert trade["id"] == "emerald:trade:PAPER-000001"
    assert trade["filledQty"] == 5
    assert {rel["type"] for rel in tr} == {"settledInPortfolio", "tradesInstrument"}


def test_map_trade_without_id_is_empty():
    assert map_trade({"status": "filled"}) == ([], [])


# --------------------------------------------------------------------------- #
# high-level snapshot
# --------------------------------------------------------------------------- #
def test_ingest_backend_snapshot_pushes_account_positions_quotes_bars():
    c = _FakeClient()
    res = ingest_backend_snapshot(
        _FakeBackend(),
        ["AAPL"],
        include_history=True,
        client=c,
        graph="__commons__",
    )
    assert res is not None and res["nodes"] > 0
    # portfolio + position + instrument + quote + bar all present
    types = {props.get("type") for props in c.txn.nodes.values()}
    assert {"Portfolio", "Position", "Instrument", "Quote", "MarketBar"} <= types


def test_snapshot_noops_without_engine():
    # No injected client -> resolves no engine -> no-op.
    assert ingest_backend_snapshot(_FakeBackend(), ["AAPL"]) is None
