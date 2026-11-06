"""The one append-only order and payment ledger (CONN-EMERALD-EXCHANGE-X402-R010.1, R015).

JSON lines under an exclusive file lock. Exchange orders and wallet sends
share one record shape, so one listing covers both venues and the trailing
spend totals survive a restart.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from scion_sdk.file_lock import lock_exclusive, lock_shared, unlock

#: Statuses that never moved value; they do not count against a limit.
NOT_SPENT = frozenset({"failed", "refused", "rejected", "cancelled"})


@dataclass(frozen=True)
class OrderRecord:
    """One order or payment on either venue."""

    venue: str
    order_id: str
    side: str
    asset: str
    amount: str
    status: str
    mode: str
    request_id: str = ""
    reference: str = ""
    kind: str = ""
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaymentLedger:
    """Append-only JSON-lines ledger at ``path``."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def append(self, record: OrderRecord) -> OrderRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            lock_exclusive(fd)
            os.write(fd, (json.dumps(record.as_dict(), sort_keys=True) + "\n").encode())
        finally:
            unlock(fd)
            os.close(fd)
        return record

    def _lines(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as handle:
            lock_shared(handle.fileno())
            try:
                for line in handle:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
            finally:
                unlock(handle.fileno())

    def records(self, venue: str = "all", limit: int = 50) -> list[dict[str, Any]]:
        """Newest first; ``venue`` is ``all``, ``exchange`` or ``wallet``."""
        rows = [r for r in self._lines() if venue == "all" or r.get("venue") == venue]
        return list(reversed(rows))[: max(0, limit)]

    def find(self, request_id: str) -> dict[str, Any] | None:
        if not request_id:
            return None
        found = None
        for row in self._lines():
            if row.get("request_id") == request_id:
                found = row
        return found

    def spent_since(self, asset: str, mode: str, *, hours: int = 24) -> Decimal:
        """Total wallet amount for ``asset`` in ``mode`` over the trailing window."""
        since = datetime.now(UTC) - timedelta(hours=hours)
        total = Decimal(0)
        for row in self._lines():
            if (
                row.get("venue") != "wallet"
                or row.get("asset") != asset
                or row.get("mode") != mode
                or row.get("status") in NOT_SPENT
            ):
                continue
            try:
                at = datetime.fromisoformat(str(row.get("at")))
                amount = Decimal(str(row.get("amount")))
            except (ValueError, InvalidOperation):
                continue
            if at >= since:
                total += amount
        return total
