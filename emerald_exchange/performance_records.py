"""Activity records the performance engine reads: valuation, cash flows, benchmark levels.

Each builder returns one finance ``Activity`` record: a stable ``record_id``
plus the ``fields`` mapping of RDF terms (IRIs and typed or plain literals)
that the engine decodes. Money is a decimal string, never a float. Identity is
a digest of the record's natural key, so reading the same event twice gives the
same ``record_id``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

#: Only the local name of an IRI term is read, so any stable base works.
IRI_BASE = "http://example.org/markets#"
VALUATION_POSITION = "account-value"
CASH_POSITION = "account-cash"
BENCHMARK_ACCOUNT = "account-benchmark"
ACCOUNT_SESSION = "account"
DEFAULT_BAR_SESSION = "regular"

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


def _iri(name: str) -> str:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("finance record name is not a valid identifier")
    return f"<{IRI_BASE}{name}>"


def decimal_text(value: Any) -> str:
    """Fixed-point decimal text of a finite number, never exponent notation."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise TypeError("finance amount must be a number")
    number = Decimal(repr(value) if isinstance(value, float) else str(value))
    if not number.is_finite():
        raise ValueError("finance amount must be finite")
    return format(number, "f")


def _decimal(value: Any) -> str:
    return f'"{decimal_text(value)}"^^xsd:decimal'


def _instant(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("finance record needs a timezone-aware instant")
    text = value.astimezone(UTC).isoformat(timespec="seconds")
    return f'"{text.replace("+00:00", "Z")}"^^xsd:dateTime'


def _currency(code: Any) -> str:
    if not isinstance(code, str) or not _CURRENCY.fullmatch(code):
        raise ValueError("finance record currency must be a three-letter code")
    return f'"{code}"'


def _record(
    kind: str,
    key: list[Any],
    fields: dict[str, str],
    *,
    source: str,
    session: str,
) -> dict[str, Any]:
    record_id = hashlib.sha256(
        json.dumps([kind, *key], ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "record_id": record_id,
        "fields": {
            "activityKind": f'"{kind}"',
            **fields,
            "recordSource": f'"{source}"',
            "activitySession": f'"{session}"',
        },
    }


def cash_flow_record(
    *,
    tenant_id: str,
    account_id: str,
    action: str,
    amount: Any,
    currency: str,
    occurred_at: datetime,
    event_id: str,
    source: str,
) -> dict[str, Any]:
    """An external cash flow; the amount is positive and ``action`` gives the sign."""
    if action not in {"deposit", "withdrawal"}:
        raise ValueError("cash flow action must be deposit or withdrawal")
    if Decimal(decimal_text(amount)) <= 0:
        raise ValueError("cash flow amount must be positive")
    return _record(
        action,
        [tenant_id, account_id, event_id],
        {
            "activityAccount": _iri(account_id),
            "activityPosition": _iri(CASH_POSITION),
            "activityTradeDate": _instant(occurred_at),
            "activityAmount": _decimal(amount),
            "activityCurrency": _currency(currency),
        },
        source=source,
        session=ACCOUNT_SESSION,
    )
