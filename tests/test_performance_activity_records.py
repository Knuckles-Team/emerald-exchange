"""The broker and market sources write the records the return engine reads."""

from types import SimpleNamespace

import pytest
from scion_sdk.ingest.live_declaration import load_declaration as declaration

from emerald_exchange.backends import AlpacaBackend, PaperBackend
from emerald_exchange.exchange_operations import READ_OPERATIONS, ExchangeReadOperations
from emerald_exchange.performance_records import account_binding_fields
from tests.test_alpaca_csv_activity_source import MAPPING
from tests.test_alpaca_stock_bars import ARGS, BAR, Market

BASE = "http://example.org/markets#"
CASH_CSV = (
    "date,side,qty,price,fee,ccy,settle\n"
    "2026-01-02T00:00:00Z,deposit,500.25,1,0,USD,2026-01-02T00:00:00Z\n"
    "2026-01-03T00:00:00Z,withdrawal,100,1,0,USD,2026-01-03T00:00:00Z\n"
    "2026-01-04T00:00:00Z,buy,10,100.5,1,USD,2026-01-06T00:00:00Z\n"
)


def broker(equity="1234.5", account_id="account-1"):
    backend = AlpacaBackend()
    backend._client = SimpleNamespace(
        get_account=lambda: SimpleNamespace(
            id=account_id, currency="USD", equity=equity, cash="9", buying_power="8"
        ),
        get_all_positions=lambda: [],
    )
    return ExchangeReadOperations(backend)


def sources():
    return {s.source_id: s for s in declaration("emerald_exchange").sources}


def cash_records():
    return broker().get_csv_activities(
        CASH_CSV, MAPPING, "tenant-1", "ABC", "licensed", "delta"
    )


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R016")
def test_csv_deposit_rows_become_deposit_records():
    result = cash_records()
    deposit, _withdrawal, trade = result["records"]
    assert deposit["fields"] == {
        "activityKind": '"deposit"',
        "activityAccount": f"<{BASE}account-1>",
        "activityPosition": f"<{BASE}account-cash>",
        "activityTradeDate": '"2026-01-02T00:00:00Z"^^xsd:dateTime',
        "activityAmount": '"500.25"^^xsd:decimal',
        "activityCurrency": '"USD"',
        "recordSource": '"alpaca-csv-activities"',
        "activitySession": '"account"',
    }
    assert "fields" not in trade
    assert len({r["record_id"] for r in result["records"]}) == 3
    again = cash_records()
    assert [r["record_id"] for r in again["records"]] == [
        r["record_id"] for r in result["records"]
    ]


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R017")
def test_csv_withdrawal_rows_become_positive_amount_withdrawal_records():
    withdrawal = cash_records()["records"][1]
    assert withdrawal["fields"]["activityKind"] == '"withdrawal"'
    assert withdrawal["fields"]["activityAmount"] == '"100.0"^^xsd:decimal'
    assert withdrawal["fields"]["activityPosition"] == f"<{BASE}account-cash>"


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R016")
def test_zero_cash_amount_is_refused():
    zero = (
        CASH_CSV.splitlines()[0]
        + "\n2026-01-02T00:00:00Z,deposit,0,1,0,USD,2026-01-02T00:00:00Z\n"
    )
    with pytest.raises(ValueError, match="Invalid CSV"):
        broker().get_csv_activities(
            zero, MAPPING, "tenant-1", "ABC", "licensed", "delta"
        )


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R018")
def test_account_valuation_is_a_decimal_account_value_record():
    assert "get_account_valuation" in READ_OPERATIONS
    source = sources()["alpaca-account-valuations"]
    assert source.tools == ("emerald_exchange_get_account_valuation",)
    result = broker().get_account_valuation("tenant-1", "delta")
    (record,) = result["records"]
    fields = record["fields"]
    assert fields["activityKind"] == '"valuation"'
    assert fields["activityPosition"] == f"<{BASE}account-value>"
    assert fields["activityAccount"] == f"<{BASE}account-1>"
    assert fields["activityMarketValue"] == '"1234.5"^^xsd:decimal'
    assert fields["activityCurrency"] == '"USD"'
    assert fields["activityTradeDate"].endswith('Z"^^xsd:dateTime')
    assert fields["recordSource"] == '"alpaca-account-valuations"'


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R018")
def test_account_valuation_refuses_bad_backend_and_non_finite_value():
    with pytest.raises(ValueError, match="Alpaca"):
        ExchangeReadOperations(PaperBackend()).get_account_valuation("t", "delta")
    with pytest.raises(ValueError, match="tenant"):
        broker().get_account_valuation(" ", "delta")
    with pytest.raises(RuntimeError):
        broker("nan").get_account_valuation("tenant-1", "delta")


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R019")
def test_bars_become_account_free_benchmark_levels():
    assert "get_benchmark_levels" in READ_OPERATIONS
    source = sources()["alpaca-benchmark-levels"]
    assert source.tools == ("emerald_exchange_get_benchmark_levels",)
    backend = AlpacaBackend()
    market = Market({"bars": {"SPY": [BAR]}, "next_page_token": None})
    backend._stock_data_client = market
    args = {**ARGS, "symbol": "SPY"}
    result = ExchangeReadOperations(backend).get_benchmark_levels(
        tenant_id="tenant-1", benchmark="SPX", **args
    )
    (record,) = result["records"]
    assert record["fields"] == {
        "activityKind": '"benchmark_level"',
        "activityAccount": f"<{BASE}account-benchmark>",
        "activityPosition": f"<{BASE}SPX>",
        "activityTradeDate": '"2026-01-02T14:30:00Z"^^xsd:dateTime',
        "activityPrice": '"102.0"^^xsd:decimal',
        "recordSource": '"alpaca-stock-bars:iex"',
        "activitySession": '"regular"',
    }
    assert result["next_page_token"] is None


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R019")
def test_benchmark_name_must_be_an_identifier_and_level_positive():
    backend = AlpacaBackend()
    backend._stock_data_client = Market(
        {"bars": {"SPY": [BAR]}, "next_page_token": None}
    )
    ops = ExchangeReadOperations(backend)
    with pytest.raises(ValueError, match="identifier"):
        ops.get_benchmark_levels(
            tenant_id="t", benchmark="S P>X", **{**ARGS, "symbol": "SPY"}
        )
    with pytest.raises(ValueError, match="tenant"):
        ops.get_benchmark_levels(
            tenant_id="", benchmark="SPX", **{**ARGS, "symbol": "SPY"}
        )


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R020")
def test_account_record_carries_a_verified_binding_state():
    (record,) = broker().get_account_snapshot()
    assert record["account_id"] == "account-1"
    assert record["fields"] == {"accountBindingState": '"verified"'}


@pytest.mark.spec("CONN-EMERALD-EXCHANGE-OPS-R020")
def test_account_without_a_valid_identity_gets_no_binding_state():
    with pytest.raises(RuntimeError, match="account read failed"):
        broker(account_id="").get_account_snapshot()
    with pytest.raises(ValueError, match="identifier"):
        account_binding_fields("a b>")
