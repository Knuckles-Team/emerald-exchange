"""Polymarket V2 Fee Model — CONCEPT:EX-AHE.harness.ee-21.

Category-aware taker fee / maker rebate schedule for the Polymarket CLOB v2
maker-rebate program. Fees are charged on the *proceeds* of a fill — i.e. on the
shares received valued at the trade price — symmetric across YES/NO so the model
uses ``min(price, 1 - price)`` as the effective per-share notional, matching the
binary-payoff structure of prediction-market contracts.

Pure arithmetic only: no engine round-trip is needed for a per-fill fee, so this
stays inline (per the package rule to keep trivial per-order math local).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FeeCategory(StrEnum):
    """Polymarket market categories with distinct fee schedules."""

    FINANCE = "finance"
    CRYPTO = "crypto"
    POLITICS = "politics"
    TECH = "tech"
    SPORTS = "sports"
    GEOPOLITICS = "geopolitics"
    OTHER = "other"


@dataclass(frozen=True)
class FeeSchedule:
    """A taker fee rate and a maker-rebate fraction (of the taker fee)."""

    taker_bps: float  # taker fee in basis points of notional
    maker_rebate_pct: float  # rebate as a fraction of the taker fee (0..1)


# Category table from the Polymarket V2 maker-rebate program.
#   taker_bps = taker fee in basis points (100 bps = 1.00%).
#   maker_rebate_pct = fraction of the taker fee paid back to the resting maker.
FEE_TABLE: dict[FeeCategory, FeeSchedule] = {
    FeeCategory.FINANCE: FeeSchedule(taker_bps=100.0, maker_rebate_pct=0.50),
    FeeCategory.CRYPTO: FeeSchedule(taker_bps=180.0, maker_rebate_pct=0.20),
    FeeCategory.POLITICS: FeeSchedule(taker_bps=100.0, maker_rebate_pct=0.25),
    FeeCategory.TECH: FeeSchedule(taker_bps=100.0, maker_rebate_pct=0.25),
    FeeCategory.SPORTS: FeeSchedule(taker_bps=75.0, maker_rebate_pct=0.0),
    FeeCategory.GEOPOLITICS: FeeSchedule(taker_bps=0.0, maker_rebate_pct=0.0),
    FeeCategory.OTHER: FeeSchedule(taker_bps=100.0, maker_rebate_pct=0.25),
}


def _category(category: str | FeeCategory) -> FeeCategory:
    if isinstance(category, FeeCategory):
        return category
    try:
        return FeeCategory(str(category).strip().lower())
    except ValueError:
        return FeeCategory.OTHER


def _effective_notional(price: float, size: float) -> float:
    """Binary-payoff effective notional per the symmetric YES/NO fee base.

    A share has min payoff distance ``min(p, 1-p)`` from its nearer boundary; the
    fee base uses this so buying YES at 0.97 is not over-charged relative to the
    equivalent NO at 0.03.
    """
    p = min(max(price, 0.0), 1.0)
    return min(p, 1.0 - p) * max(size, 0.0)


def taker_fee(price: float, size: float, category: str | FeeCategory) -> float:
    """Taker fee charged when crossing the spread. CONCEPT:EX-AHE.harness.ee-21.

    Args:
        price: fill price in (0, 1).
        size: number of contracts/shares filled.
        category: market category (enum or string).

    Returns:
        Fee in quote currency (USDC), always >= 0.
    """
    sched = FEE_TABLE[_category(category)]
    return _effective_notional(price, size) * (sched.taker_bps / 10_000.0)


def maker_rebate(price: float, size: float, category: str | FeeCategory) -> float:
    """Maker rebate credited when a resting order is filled. CONCEPT:EX-AHE.harness.ee-21.

    Returns a positive credit (subtract from cost / add to PnL).
    """
    sched = FEE_TABLE[_category(category)]
    gross = _effective_notional(price, size) * (sched.taker_bps / 10_000.0)
    return gross * sched.maker_rebate_pct


def net_fee(
    price: float, size: float, category: str | FeeCategory, *, is_maker: bool
) -> float:
    """Signed fee for a fill: positive = cost, negative = net credit.

    Takers always pay ``taker_fee``. Makers pay nothing and *receive* the rebate,
    so their net fee is ``-maker_rebate`` (a credit).
    """
    if is_maker:
        return -maker_rebate(price, size, category)
    return taker_fee(price, size, category)
