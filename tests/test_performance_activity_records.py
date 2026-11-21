"""The broker and market sources write the records the return engine reads."""

from types import SimpleNamespace

import pytest

from emerald_exchange.backends import AlpacaBackend
from emerald_exchange.exchange_operations import ExchangeReadOperations
from tests.test_alpaca_csv_activity_source import MAPPING

BASE = "http://example.org/markets#"
CASH_CSV = (
    "date,side,qty,price,fee,ccy,settle\n"
    "2026-01-02T00:00:00Z,deposit,500.25,1,0,USD,2026-01-02T00:00:00Z\n"
    "2026-01-03T00:00:00Z,withdrawal,100,1,0,USD,2026-01-03T00:00:00Z\n"
    "2026-01-04T00:00:00Z,buy,10,100.5,1,USD,2026-01-06T00:00:00Z\n"
)


def broker(equity="1234.5"):
    backend = AlpacaBackend()
    backend._client = SimpleNamespace(
        get_account=lambda: SimpleNamespace(
            id="account-1", currency="USD", equity=equity, cash="9", buying_power="8"
        )
    )
    return ExchangeReadOperations(backend)


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
