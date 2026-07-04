"""Live Trading Cockpit (text-mode) — CONCEPT:AU-AHE.assimilation.microstructure-signal-fusion

A real, GUI-free cockpit that renders live trading state as a structured
snapshot plus a plain-text (or ``rich``, when installed) table render. This is
the functional core of a FinceptTerminal-style cockpit, text-mode:

  * engine status (epistemic-graph reachable? — via the lazy ``_engine``),
  * account / positions (via any bound ``ExchangeBackend``),
  * risk status (halt / kill-switch, drawdown, daily-loss) from ``RiskGuard``,
  * recent quotes for a watchlist,
  * recent signals fed in by the caller.

It MUST work offline: a missing engine renders ``engine: offline``, a backend
error renders an empty/zeroed panel rather than raising. Nothing here places an
order — the cockpit is read-only.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from emerald_exchange.backends import ExchangeBackend, PaperBackend
from emerald_exchange.risk_guards import RiskGuard

logger = logging.getLogger(__name__)


@dataclass
class CockpitSnapshot:
    """Structured, serializable cockpit state at one instant."""

    timestamp: str
    engine: dict[str, Any]
    account: dict[str, Any]
    positions: list[dict[str, Any]]
    risk: dict[str, Any]
    quotes: list[dict[str, Any]]
    signals: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def _engine_status() -> dict[str, Any]:
    """Probe the epistemic-graph engine without ever raising.

    Returns ``{"status": "online"|"offline", ...}``. A reachable client also
    reports a lightweight health ping when the client exposes one.
    """
    try:
        from emerald_exchange._engine import finance_engine

        client = finance_engine()
    except Exception as exc:  # noqa: BLE001 — cockpit never crashes on probe
        return {"status": "offline", "detail": f"probe error: {exc}"}

    if client is None:
        return {"status": "offline", "detail": "engine unreachable"}

    info: dict[str, Any] = {"status": "online", "detail": "quant compute enabled"}
    # Optional health ping — tolerate clients that don't expose one.
    for attr in ("ping", "health"):
        fn = getattr(client, attr, None)
        if callable(fn):
            try:
                info["health"] = fn()
            except Exception as exc:  # noqa: BLE001
                info["health"] = f"{attr} failed: {exc}"
            break
    return info


def _account_panel(backend: ExchangeBackend) -> dict[str, Any]:
    try:
        acct = backend.get_account()
        return {
            "exchange": backend.name,
            "mode": str(backend.mode),
            "equity": acct.equity,
            "cash": acct.cash,
            "buying_power": acct.buying_power,
            "currency": acct.currency,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "exchange": getattr(backend, "name", "?"),
            "mode": "unknown",
            "equity": 0.0,
            "cash": 0.0,
            "buying_power": 0.0,
            "error": str(exc),
        }


def _positions_panel(backend: ExchangeBackend) -> list[dict[str, Any]]:
    try:
        return [
            {
                "symbol": p.symbol,
                "qty": p.qty,
                "side": p.side,
                "avg_entry": p.avg_entry_price,
                "current": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in backend.get_positions()
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("positions lookup failed: %s", exc)
        return []


def _risk_panel(backend: ExchangeBackend, risk_guard: RiskGuard) -> dict[str, Any]:
    panel: dict[str, Any] = {
        "halted": risk_guard.is_halted,
        "kill_switch": "ENGAGED" if risk_guard.is_halted else "armed",
        "peak_equity": risk_guard._peak_equity,
        "max_drawdown_pct": risk_guard.limits.max_portfolio_drawdown_pct,
        "max_daily_loss_pct": risk_guard.limits.max_daily_loss_pct,
        "require_human_approval_live": risk_guard.limits.require_human_approval_live,
    }
    try:
        equity = backend.get_account().equity
        peak = risk_guard._peak_equity
        if peak > 0:
            panel["drawdown_pct"] = max(0.0, (peak - equity) / peak)
        else:
            panel["drawdown_pct"] = 0.0
    except Exception as exc:  # noqa: BLE001
        panel["drawdown_pct"] = 0.0
        panel["detail"] = str(exc)
    return panel


def _quotes_panel(
    backend: ExchangeBackend, watchlist: list[str]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for symbol in watchlist:
        try:
            q = backend.get_quote(symbol)
            out.append(
                {
                    "symbol": q.symbol,
                    "bid": q.bid,
                    "ask": q.ask,
                    "last": q.last,
                    "volume": q.volume,
                }
            )
        except Exception as exc:  # noqa: BLE001
            out.append({"symbol": symbol, "error": str(exc)})
    return out


def build_snapshot(
    backend: ExchangeBackend,
    risk_guard: RiskGuard,
    watchlist: list[str] | None = None,
    signals: list[dict[str, Any]] | None = None,
) -> CockpitSnapshot:
    """Assemble a full cockpit snapshot. Never raises; degrades per-panel."""
    return CockpitSnapshot(
        timestamp=datetime.now(UTC).isoformat(),
        engine=_engine_status(),
        account=_account_panel(backend),
        positions=_positions_panel(backend),
        risk=_risk_panel(backend, risk_guard),
        quotes=_quotes_panel(backend, watchlist or []),
        signals=list(signals or []),
    )


def _plain_table(title: str, rows: list[tuple[str, str]]) -> str:
    width = max((len(k) for k, _ in rows), default=4)
    lines = [f"── {title} " + "─" * max(0, 40 - len(title))]
    for k, v in rows:
        lines.append(f"  {k.ljust(width)} : {v}")
    return "\n".join(lines)


def render_snapshot(snapshot: CockpitSnapshot, use_rich: bool = True) -> str:
    """Render a snapshot to a string. Uses ``rich`` when available+requested,
    else a clean plain-text layout. Always returns text (never prints)."""
    if use_rich:
        try:
            return _render_rich(snapshot)
        except Exception as exc:  # noqa: BLE001 — fall back to plain text
            logger.debug("rich render failed, falling back to plain: %s", exc)
    return _render_plain(snapshot)


def _render_plain(s: CockpitSnapshot) -> str:
    eng = s.engine
    blocks: list[str] = []
    blocks.append(f"╔══ EMERALD COCKPIT ══ {s.timestamp} ══╗")
    blocks.append(
        _plain_table(
            "ENGINE",
            [
                ("status", eng.get("status", "?")),
                ("detail", str(eng.get("detail", ""))),
            ],
        )
    )
    a = s.account
    blocks.append(
        _plain_table(
            "ACCOUNT",
            [
                ("exchange", str(a.get("exchange", "?"))),
                ("mode", str(a.get("mode", "?"))),
                ("equity", f"{a.get('equity', 0.0):,.2f} {a.get('currency', '')}"),
                ("cash", f"{a.get('cash', 0.0):,.2f}"),
                ("buying_power", f"{a.get('buying_power', 0.0):,.2f}"),
            ],
        )
    )
    r = s.risk
    blocks.append(
        _plain_table(
            "RISK",
            [
                ("kill_switch", str(r.get("kill_switch", "?"))),
                ("halted", str(r.get("halted", "?"))),
                ("drawdown", f"{r.get('drawdown_pct', 0.0):.2%}"),
                ("max_drawdown", f"{r.get('max_drawdown_pct', 0.0):.2%}"),
                ("max_daily_loss", f"{r.get('max_daily_loss_pct', 0.0):.2%}"),
                ("live_approval", str(r.get("require_human_approval_live", "?"))),
            ],
        )
    )
    if s.positions:
        pos_rows = [
            (
                p["symbol"],
                f"{p['qty']:.4f} @ {p['current']:.2f} (uPnL {p['unrealized_pnl']:+.2f})",
            )
            for p in s.positions
        ]
    else:
        pos_rows = [("(none)", "flat")]
    blocks.append(_plain_table("POSITIONS", pos_rows))
    if s.quotes:
        q_rows = [
            (
                q.get("symbol", "?"),
                (
                    f"bid {q['bid']:.2f} / ask {q['ask']:.2f} / last {q['last']:.2f}"
                    if "error" not in q
                    else f"error: {q['error']}"
                ),
            )
            for q in s.quotes
        ]
        blocks.append(_plain_table("QUOTES", q_rows))
    if s.signals:
        sig_rows = [
            (
                str(sig.get("name", sig.get("symbol", f"sig{i}"))),
                str(sig.get("value", sig)),
            )
            for i, sig in enumerate(s.signals)
        ]
        blocks.append(_plain_table("SIGNALS", sig_rows))
    blocks.append("╚" + "═" * 38 + "╝")
    return "\n\n".join(blocks)


def _render_rich(s: CockpitSnapshot) -> str:
    from io import StringIO

    from rich.console import Console
    from rich.table import Table

    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=80)

    eng_ok = s.engine.get("status") == "online"
    header = Table(title=f"EMERALD COCKPIT — {s.timestamp}", expand=True)
    header.add_column("Field")
    header.add_column("Value")
    header.add_row("engine", "[green]online[/]" if eng_ok else "[red]offline[/]")
    header.add_row("exchange", str(s.account.get("exchange", "?")))
    header.add_row("mode", str(s.account.get("mode", "?")))
    header.add_row(
        "kill_switch",
        "[red]ENGAGED[/]" if s.risk.get("halted") else "[green]armed[/]",
    )
    header.add_row("equity", f"{s.account.get('equity', 0.0):,.2f}")
    header.add_row("drawdown", f"{s.risk.get('drawdown_pct', 0.0):.2%}")
    console.print(header)

    if s.positions:
        pt = Table(title="Positions")
        for col in ("symbol", "qty", "current", "uPnL"):
            pt.add_column(col)
        for p in s.positions:
            pt.add_row(
                p["symbol"],
                f"{p['qty']:.4f}",
                f"{p['current']:.2f}",
                f"{p['unrealized_pnl']:+.2f}",
            )
        console.print(pt)

    if s.quotes:
        qt = Table(title="Quotes")
        for col in ("symbol", "bid", "ask", "last"):
            qt.add_column(col)
        for q in s.quotes:
            if "error" in q:
                qt.add_row(q.get("symbol", "?"), "-", "-", f"err: {q['error']}")
            else:
                qt.add_row(
                    q["symbol"],
                    f"{q['bid']:.2f}",
                    f"{q['ask']:.2f}",
                    f"{q['last']:.2f}",
                )
        console.print(qt)

    return buf.getvalue()


def cockpit(
    backend: ExchangeBackend | None = None,
    risk_guard: RiskGuard | None = None,
    watchlist: list[str] | None = None,
    signals: list[dict[str, Any]] | None = None,
    as_json: bool = False,
    use_rich: bool = True,
) -> str:
    """Build + render a cockpit view. Callable from code or the CLI.

    With no backend/risk_guard, defaults to a connected ``PaperBackend`` and a
    default ``RiskGuard`` so the cockpit always renders (offline-safe).
    """
    if backend is None:
        backend = PaperBackend()
        backend.connect()
    if risk_guard is None:
        risk_guard = RiskGuard()
    snap = build_snapshot(backend, risk_guard, watchlist, signals)
    if as_json:
        return snap.to_json()
    return render_snapshot(snap, use_rich=use_rich)


def main(argv: list[str] | None = None) -> int:
    """Console-script entry: ``emerald-cockpit``."""
    parser = argparse.ArgumentParser(
        prog="emerald-cockpit",
        description="Live text-mode trading cockpit for emerald-exchange.",
    )
    parser.add_argument(
        "--watch",
        default="",
        help="Comma-separated watchlist symbols (e.g. AAPL,BTC/USD).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit the structured snapshot as JSON."
    )
    parser.add_argument(
        "--no-rich", action="store_true", help="Force plain-text render."
    )
    args = parser.parse_args(argv)

    watchlist = [s.strip() for s in args.watch.split(",") if s.strip()]
    backend = PaperBackend()
    backend.connect()
    risk_guard = RiskGuard()

    out = cockpit(
        backend=backend,
        risk_guard=risk_guard,
        watchlist=watchlist,
        as_json=args.json,
        use_rich=not args.no_rich,
    )
    print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
