"""Run stock provider fixture packs through the SDK adapter and real graph."""

from importlib import import_module
from importlib.metadata import version

import pytest
from packaging.version import Version

from tests.live_engine import live_compute as _live_compute


@pytest.fixture
def stock_adapter_engine(tmp_path_factory):
    yield from _live_compute.__wrapped__(tmp_path_factory)


@pytest.mark.skipif(
    Version(version("epistemic-graph")) < Version("2.27.6"),
    reason="real connector pack replay requires graph 2.27.6",
)
@pytest.mark.parametrize(
    ("module_name", "test_name"),
    [
        (
            "tests.test_alpaca_stock_bars_graph",
            "test_served_stock_pages_reimport_into_graph",
        ),
        (
            "tests.test_alpaca_stock_events_graph",
            "test_served_stock_events_reimport_into_graph",
        ),
        (
            "tests.test_fmp_company_sources_graph",
            "test_served_company_sources_reimport_into_graph",
        ),
    ],
)
def test_stock_adapter_replays_provider_sources(
    stock_adapter_engine, monkeypatch, module_name, test_name
):
    stock = pytest.importorskip("agent_connector_sdk.finance.stock_source")
    module = import_module(module_name)
    source_class = module.McpToolSourceAdapter
    kinds = {
        "StockBar": "bar",
        "StockQuote": "quote",
        "StockNews": "news",
        "StockDividend": "dividend",
    }

    def validated_source(preset, **kwargs):
        mapping = kwargs["mapping_reference"].rsplit("/", 1)[-1]
        kind = (
            preset.params["dataset"] if mapping == "CompanyRecord" else kinds[mapping]
        )
        source = source_class(preset, **kwargs)
        return stock.StockSourceAdapter(
            source, stock_kind=stock.StockSourceKind(kind), symbol="AAPL"
        )

    monkeypatch.setattr(module, "McpToolSourceAdapter", validated_source)
    getattr(module, test_name)(stock_adapter_engine, monkeypatch)
