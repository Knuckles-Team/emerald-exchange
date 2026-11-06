"""Server-side admission for every wallet send (CONN-EMERALD-EXCHANGE-X402-R010.1).

Composes the shared kill switch of ``RiskGuard`` with per-asset limits read
from config and trailing totals read from the ledger. No limit is
hard-coded: an asset with no configured limit is refused.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from emerald_exchange.payments.ledger import PaymentLedger
from emerald_exchange.payments.refusals import PaymentRefused
from emerald_exchange.risk_guards import RiskGuard

DEFAULT_BREAKER_FAILURES = 3


def parse_amount(raw: object) -> Decimal:
    """A strictly positive, finite decimal amount, else ``PAYMENTS_AMOUNT_INVALID``."""
    try:
        amount = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise PaymentRefused("PAYMENTS_AMOUNT_INVALID") from None
    if not amount.is_finite() or amount <= 0:
        raise PaymentRefused("PAYMENTS_AMOUNT_INVALID")
    return amount


def asset_key(network: str, token: str = "") -> str:
    """``<network>:<token>`` with ``native`` for the gas asset."""
    return f"{network.strip().lower()}:{(token or 'native').strip().lower()}"


@dataclass(frozen=True)
class Admission:
    """An admitted send: the mode it runs in and the amount admitted."""

    mode: str
    amount: Decimal


class PaymentGovernor:
    """Kill switch, live opt-in, per-asset limits, approval threshold, breaker."""

    def __init__(
        self, risk_guard: RiskGuard, ledger: PaymentLedger, config: Mapping[str, Any]
    ) -> None:
        self.risk_guard = risk_guard
        self.ledger = ledger
        self.config = config
        self._failures = 0

    @property
    def mode(self) -> str:
        live = (
            str(self.config.get("mode", "paper")).lower() == "live"
            and self.config.get("live_opt_in") is True
        )
        return "live" if live else "paper"

    def limits(self) -> dict[str, Any]:
        """The configured limits and approval thresholds (read-only view)."""
        return {
            "mode": self.mode,
            "limits": dict(self.config.get("limits", {})),
            "approve_above": dict(self.config.get("approve_above", {})),
            "breaker_failures": self._breaker_threshold(),
        }

    def _breaker_threshold(self) -> int:
        try:
            value = int(self.config.get("breaker_failures", DEFAULT_BREAKER_FAILURES))
        except (TypeError, ValueError):
            value = DEFAULT_BREAKER_FAILURES
        return min(max(value, 1), 20)

    def _limit(self, asset: str, scope: str) -> Decimal:
        entry = self.config.get("limits", {}).get(asset)
        if not isinstance(entry, Mapping) or entry.get(scope) in (None, ""):
            raise PaymentRefused("SPEND_LIMIT_UNSET", asset=asset, scope=scope)
        try:
            return Decimal(str(entry[scope]))
        except InvalidOperation:
            raise PaymentRefused(
                "SPEND_LIMIT_UNSET", asset=asset, scope=scope
            ) from None

    def admit(self, asset: str, raw_amount: object) -> Admission:
        """Admit one send of ``raw_amount`` of ``asset`` or raise ``PaymentRefused``."""
        if self.risk_guard.is_halted:
            raise PaymentRefused("KILL_SWITCH_ACTIVE")
        amount = parse_amount(raw_amount)
        per_tx = self._limit(asset, "per_tx")
        daily = self._limit(asset, "daily")
        mode = self.mode
        if amount > per_tx:
            raise PaymentRefused("SPEND_LIMIT_EXCEEDED", asset=asset, scope="per_tx")
        if self.ledger.spent_since(asset, mode) + amount > daily:
            raise PaymentRefused("SPEND_LIMIT_EXCEEDED", asset=asset, scope="daily")
        threshold = self.config.get("approve_above", {}).get(asset)
        if threshold not in (None, "") and amount > Decimal(str(threshold)):
            raise PaymentRefused("APPROVAL_REQUIRED", asset=asset)
        return Admission(mode=mode, amount=amount)

    def record_success(self) -> None:
        self._failures = 0

    def record_failure(self) -> None:
        """Count a runtime failure; trip the shared kill switch at the threshold."""
        self._failures += 1
        if self._failures >= self._breaker_threshold():
            self.risk_guard.halt("payments breaker: consecutive runtime failures")
            raise PaymentRefused("BREAKER_OPEN", failures=self._failures)
