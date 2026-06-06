"""Polymarket wallet-intelligence provider — CONCEPT:EE-028.

Folded into emerald-exchange from the former standalone ``poly-wallet-mcp``
package. Smart-money analytics over a ``poly_data`` trade dataset: find
smart-money wallets, profile them, measure convergence on a token, and study
exit behavior.

All analytics are pure-Python over the normalized trade records, so they run
without ``polars`` installed. ``polars`` is an *optional* fast loader (and
required for ``.parquet``); when absent the stdlib ``csv`` module is used so
importing this module never hard-fails. When no dataset path is configured (or
the file is missing), operations raise a clear ``NoDatasetConfigured`` error.

Normalized per-trade record (one row = one fill from the wallet's perspective):

    wallet        str    the trader address (proxyWallet / maker / taker)
    market_id     str    Polymarket market id
    token         str    outcome token id (asset_id)
    side          str    "BUY" | "SELL" (wallet's direction in the outcome token)
    price         float  fill price in [0, 1]
    usd_amount    float  USDC notional of the fill
    shares        float  outcome-token quantity
    timestamp     int    unix seconds
    resolved      bool   whether the market has resolved (optional)
    won           bool   whether this wallet's position won (optional)
    payout        float  realized payout for the position (optional)
"""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from typing import Any

TRADE_FIELDS = (
    "wallet",
    "market_id",
    "token",
    "side",
    "price",
    "usd_amount",
    "shares",
    "timestamp",
    "resolved",
    "won",
    "payout",
)

# Aliases mapping poly_data raw column names → normalized fields.
COLUMN_ALIASES: dict[str, str] = {
    "proxyWallet": "wallet",
    "maker": "wallet",
    "taker": "wallet",
    "user": "wallet",
    "marketId": "market_id",
    "market": "market_id",
    "asset_id": "token",
    "assetId": "token",
    "nonusdc_asset_id": "token",
    "outcome_token": "token",
    "taker_direction": "side",
    "nonusdc_side": "side",
    "direction": "side",
    "usd_amount": "usd_amount",
    "usdcSize": "usd_amount",
    "usdSize": "usd_amount",
    "size": "shares",
    "shares_amount": "shares",
    "ts": "timestamp",
    "time": "timestamp",
}


class NoDatasetConfigured(RuntimeError):
    """Raised when a wallet operation needs trade data but none is configured."""


def _coerce(record: dict[str, Any]) -> dict[str, Any]:
    """Apply column aliases and type coercion to one raw row."""
    out: dict[str, Any] = {}
    for k, v in record.items():
        key = COLUMN_ALIASES.get(k, k)
        if key in TRADE_FIELDS:
            out.setdefault(key, v)
    # numeric coercion
    for f in ("price", "usd_amount", "shares", "payout"):
        if f in out:
            out[f] = _to_float(out[f])
    if "timestamp" in out:
        out["timestamp"] = _to_int(out["timestamp"])
    for f in ("resolved", "won"):
        if f in out:
            out[f] = _to_bool(out[f])
    if "side" in out and out["side"] is not None:
        out["side"] = str(out["side"]).upper()
    if "wallet" in out and out["wallet"] is not None:
        out["wallet"] = str(out["wallet"]).lower()
    return out


class TradeDataset:
    """A loaded, normalized list of Polymarket trades."""

    def __init__(self, trades: list[dict[str, Any]], source: str | None = None) -> None:
        self.trades = trades
        self.source = source

    def __len__(self) -> int:
        return len(self.trades)

    def by_wallet(self) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for t in self.trades:
            w = t.get("wallet")
            if w:
                groups.setdefault(w, []).append(t)
        return groups


class PolyWalletApi:
    """Wallet ranking, profiling, convergence, and exit-behavior analytics.

    Loads trade datasets from a configurable path (CSV or Parquet). The dataset
    path is taken from the constructor or ``POLY_TRADES_PATH``. ``polars`` is
    used when available (and for ``.parquet``); otherwise the stdlib CSV reader
    is used for ``.csv`` files.
    """

    def __init__(self, dataset_path: str | None = None) -> None:
        self.dataset_path = dataset_path or os.getenv("POLY_TRADES_PATH", "")
        self._cache: TradeDataset | None = None

    @property
    def configured(self) -> bool:
        return bool(self.dataset_path)

    @staticmethod
    def _polars():
        try:
            import polars as pl  # type: ignore

            return pl
        except Exception:
            return None

    def load(self, force: bool = False) -> TradeDataset:
        """Load and normalize the configured trade dataset (cached)."""
        if self._cache is not None and not force:
            return self._cache
        if not self.dataset_path:
            raise NoDatasetConfigured(
                "No trade dataset configured. Set POLY_TRADES_PATH (or pass "
                "dataset_path) to a poly_data processed-trades CSV/Parquet file."
            )
        if not os.path.exists(self.dataset_path):
            raise NoDatasetConfigured(
                f"Configured trade dataset not found: {self.dataset_path!r}."
            )

        rows = self._read_rows(self.dataset_path)
        trades = [_coerce(r) for r in rows]
        self._cache = TradeDataset(trades, source=self.dataset_path)
        return self._cache

    def _read_rows(self, path: str) -> Iterable[dict[str, Any]]:
        pl = self._polars()
        if path.endswith(".parquet") or path.endswith(".pq"):
            if pl is None:
                raise NoDatasetConfigured(
                    "Parquet datasets require the optional 'polars' dependency: "
                    "pip install 'emerald-exchange[wallet_intel]'."
                )
            return pl.read_parquet(path).to_dicts()
        if pl is not None:
            try:
                return pl.read_csv(path, infer_schema_length=10_000).to_dicts()
            except Exception:
                pass
        with open(path, newline="") as fh:
            return list(csv.DictReader(fh))

    # ------------------------------------------------------------------ #
    # Per-wallet aggregation
    # ------------------------------------------------------------------ #
    def _wallet_stats(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate one wallet's trades into summary stats.

        A "position" is a (market_id, token) pair. PnL per position uses
        realized ``payout`` when present, else marks the net cash flow
        (sells add cash, buys subtract cash) — a best-effort proxy.
        """
        n_trades = len(trades)
        positions: dict[tuple, dict[str, Any]] = {}
        total_volume = 0.0
        for t in trades:
            total_volume += t.get("usd_amount", 0.0)
            key = (t.get("market_id"), t.get("token"))
            pos = positions.setdefault(
                key,
                {
                    "buy_usd": 0.0,
                    "sell_usd": 0.0,
                    "shares": 0.0,
                    "payout": 0.0,
                    "has_payout": False,
                    "won": None,
                    "resolved": False,
                    "first_ts": None,
                    "last_ts": None,
                },
            )
            side = t.get("side")
            amt = t.get("usd_amount", 0.0)
            if side == "BUY":
                pos["buy_usd"] += amt
                pos["shares"] += t.get("shares", 0.0)
            elif side == "SELL":
                pos["sell_usd"] += amt
                pos["shares"] -= t.get("shares", 0.0)
            if "payout" in t and t.get("payout"):
                pos["payout"] += t.get("payout", 0.0)
                pos["has_payout"] = True
            if t.get("won") is not None:
                pos["won"] = t.get("won")
            if t.get("resolved"):
                pos["resolved"] = True
            ts = t.get("timestamp")
            if ts:
                pos["first_ts"] = (
                    ts if pos["first_ts"] is None else min(pos["first_ts"], ts)
                )
                pos["last_ts"] = (
                    ts if pos["last_ts"] is None else max(pos["last_ts"], ts)
                )

        wins = 0
        decided = 0
        total_pnl = 0.0
        for pos in positions.values():
            if pos["has_payout"]:
                pnl = pos["payout"] + pos["sell_usd"] - pos["buy_usd"]
            else:
                pnl = pos["sell_usd"] - pos["buy_usd"]
            total_pnl += pnl
            won = pos["won"]
            if won is None and (pos["has_payout"] or pos["resolved"]):
                won = pnl > 0
            if won is not None:
                decided += 1
                wins += 1 if won else 0

        win_rate = (wins / decided) if decided else 0.0
        return {
            "n_trades": n_trades,
            "n_positions": len(positions),
            "decided_positions": decided,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "total_pnl": round(total_pnl, 2),
            "total_volume": round(total_volume, 2),
        }

    # ------------------------------------------------------------------ #
    # rank_wallets
    # ------------------------------------------------------------------ #
    def rank_wallets(
        self,
        min_trades: int = 20,
        min_win_rate: float = 0.55,
        top_k: int = 25,
    ) -> dict[str, Any]:
        """Filter wallets with >= min_trades and win_rate > min_win_rate,
        rank by total_pnl, return the top-K copy-trade targets."""
        ds = self.load()
        out = []
        for wallet, trades in ds.by_wallet().items():
            stats = self._wallet_stats(trades)
            if stats["n_trades"] < min_trades:
                continue
            if stats["win_rate"] <= min_win_rate:
                continue
            out.append({"wallet": wallet, **stats})
        out.sort(key=lambda r: r["total_pnl"], reverse=True)
        return {
            "min_trades": min_trades,
            "min_win_rate": min_win_rate,
            "count": len(out),
            "targets": out[:top_k],
        }

    # ------------------------------------------------------------------ #
    # wallet_profile
    # ------------------------------------------------------------------ #
    def wallet_profile(self, wallet: str) -> dict[str, Any]:
        """Per-wallet summary stats plus its current (unresolved) open positions."""
        ds = self.load()
        w = wallet.lower()
        trades = ds.by_wallet().get(w, [])
        if not trades:
            return {"wallet": w, "found": False, "n_trades": 0}
        stats = self._wallet_stats(trades)
        open_positions = self._open_positions(trades)
        return {
            "wallet": w,
            "found": True,
            **stats,
            "open_positions": open_positions,
        }

    @staticmethod
    def _open_positions(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        net: dict[tuple, dict[str, Any]] = {}
        for t in trades:
            key = (t.get("market_id"), t.get("token"))
            pos = net.setdefault(
                key,
                {
                    "market_id": t.get("market_id"),
                    "token": t.get("token"),
                    "net_shares": 0.0,
                    "resolved": False,
                },
            )
            sign = 1.0 if t.get("side") == "BUY" else -1.0
            pos["net_shares"] += sign * t.get("shares", 0.0)
            if t.get("resolved"):
                pos["resolved"] = True
        return [
            {
                "market_id": p["market_id"],
                "token": p["token"],
                "net_shares": round(p["net_shares"], 4),
            }
            for p in net.values()
            if not p["resolved"] and abs(p["net_shares"]) > 1e-9
        ]

    # ------------------------------------------------------------------ #
    # smart_money_convergence
    # ------------------------------------------------------------------ #
    def smart_money_convergence(
        self,
        token: str,
        wallets: list[str],
        market_id: str | None = None,
    ) -> dict[str, Any]:
        """Of a target wallet set, how many currently hold the same side
        (net long) of ``token`` (optionally scoped to ``market_id``)."""
        ds = self.load()
        groups = ds.by_wallet()
        targets = [w.lower() for w in wallets]
        holders_long = []
        holders_short = []
        for w in targets:
            net = 0.0
            for t in groups.get(w, []):
                if t.get("token") != token:
                    continue
                if market_id and t.get("market_id") != market_id:
                    continue
                sign = 1.0 if t.get("side") == "BUY" else -1.0
                net += sign * t.get("shares", 0.0)
            if net > 1e-9:
                holders_long.append({"wallet": w, "net_shares": round(net, 4)})
            elif net < -1e-9:
                holders_short.append({"wallet": w, "net_shares": round(net, 4)})
        n = len(targets) or 1
        return {
            "token": token,
            "market_id": market_id,
            "n_target_wallets": len(targets),
            "n_long": len(holders_long),
            "n_short": len(holders_short),
            "long_convergence": round(len(holders_long) / n, 4),
            "holders_long": holders_long,
            "holders_short": holders_short,
        }

    # ------------------------------------------------------------------ #
    # exit_behavior
    # ------------------------------------------------------------------ #
    def exit_behavior(self, wallet: str) -> dict[str, Any]:
        """For a wallet's positions: what % exit before resolution, and the
        average % of max profit captured (best-effort over realized payouts)."""
        ds = self.load()
        w = wallet.lower()
        trades = ds.by_wallet().get(w, [])
        if not trades:
            return {"wallet": w, "found": False}

        positions: dict[tuple, dict[str, Any]] = {}
        for t in trades:
            key = (t.get("market_id"), t.get("token"))
            pos = positions.setdefault(
                key,
                {
                    "buy_usd": 0.0,
                    "sell_usd": 0.0,
                    "shares_bought": 0.0,
                    "resolved": False,
                    "exited": False,
                    "payout": 0.0,
                    "has_payout": False,
                },
            )
            if t.get("side") == "BUY":
                pos["buy_usd"] += t.get("usd_amount", 0.0)
                pos["shares_bought"] += t.get("shares", 0.0)
            elif t.get("side") == "SELL":
                pos["sell_usd"] += t.get("usd_amount", 0.0)
                pos["exited"] = True
            if t.get("resolved"):
                pos["resolved"] = True
            if t.get("payout"):
                pos["payout"] += t.get("payout", 0.0)
                pos["has_payout"] = True

        total = len(positions)
        exited_before_res = 0
        capture_ratios = []
        for pos in positions.values():
            if pos["exited"] and not pos["resolved"]:
                exited_before_res += 1
            # Max profit if held to a winning resolution: shares pay $1 each.
            max_payout = pos["shares_bought"]  # 1.0 per share at resolution
            realized = pos["sell_usd"] + (pos["payout"] if pos["has_payout"] else 0.0)
            max_profit = max_payout - pos["buy_usd"]
            realized_profit = realized - pos["buy_usd"]
            if max_profit > 1e-9:
                capture_ratios.append(max(0.0, min(realized_profit / max_profit, 1.0)))

        avg_capture = (
            sum(capture_ratios) / len(capture_ratios) if capture_ratios else 0.0
        )
        return {
            "wallet": w,
            "found": True,
            "n_positions": total,
            "pct_exit_before_resolution": round(exited_before_res / total, 4)
            if total
            else 0.0,
            "avg_pct_max_profit_captured": round(avg_capture, 4),
        }


# --------------------------------------------------------------------------- #
# coercion helpers
# --------------------------------------------------------------------------- #
def _to_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_int(v: Any) -> int:
    if v is None or v == "":
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "won", "resolved")
