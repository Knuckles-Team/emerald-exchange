"""Production Polymarket WebSocket Client — CONCEPT:EX-AHE.harness.ee-24.

Async subscriber for the Polymarket CLOB **market channel** with the resilience
properties a live HFT feed needs:

* **Auto-reconnect with exponential backoff** (capped, with jitter).
* **Heartbeat-timeout watchdog** — detects a *silently frozen* socket (TCP open
  but no messages) and forces a reconnect, which a plain ``recv()`` loop cannot.
* **Sequence / hash gap tracking** — every book/price message is expected to
  carry a monotonically increasing sequence (or a book hash). On a gap, a
  ``resync_callback`` is invoked so the caller can re-snapshot the book via REST
  before trusting deltas again.

The repo was previously REST-only; this is the genuine streaming capability. It
depends on ``websockets`` (declared optional) and is import-safe without it — the
dependency is only required when you actually ``run()``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

MessageCallback = Callable[[dict[str, Any]], Awaitable[None]]
ResyncCallback = Callable[
    [str, int, int], Awaitable[None]
]  # (asset_id, last_seq, got_seq)


@dataclass
class WSConfig:
    url: str = DEFAULT_WS_URL
    asset_ids: list[str] = field(default_factory=list)
    heartbeat_timeout: float = 15.0  # secs without any message ⇒ assume frozen
    ping_interval: float = 5.0  # secs between client pings
    backoff_base: float = 0.5
    backoff_max: float = 30.0
    max_reconnects: int = 0  # 0 = unlimited


class PolymarketMarketStream:
    """Resilient market-channel subscriber. CONCEPT:EX-AHE.harness.ee-24."""

    def __init__(
        self,
        config: WSConfig,
        on_message: MessageCallback,
        on_resync: ResyncCallback | None = None,
    ) -> None:
        self.config = config
        self._on_message = on_message
        self._on_resync = on_resync
        self._last_msg_ts: float = 0.0
        self._last_seq: dict[str, int] = {}
        self._stop = asyncio.Event()
        self._reconnects = 0
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def stop(self) -> None:
        self._stop.set()

    # ── sequence / hash gap detection ──────────────────────────────────
    def _extract_seq(self, msg: dict[str, Any]) -> tuple[str, int] | None:
        """Pull (asset_id, sequence) from a market message, if present."""
        asset = msg.get("asset_id") or msg.get("market") or msg.get("token_id") or ""
        seq = msg.get("seq")
        if seq is None:
            seq = msg.get("sequence")
        if seq is None:
            h = msg.get("hash")
            if h is not None:
                # Hash-based feeds: track equality, not ordering. Encode as a
                # stable int so the same gap machinery applies.
                seq = abs(hash(h)) % (10**12)
        if asset and seq is not None:
            try:
                return str(asset), int(seq)
            except (TypeError, ValueError):
                return None
        return None

    async def _check_gap(self, msg: dict[str, Any]) -> None:
        info = self._extract_seq(msg)
        if info is None:
            return
        asset, seq = info
        last = self._last_seq.get(asset)
        # A gap is any non-consecutive increase (seq feeds) — we tolerate equal
        # (duplicate) and strictly +1. Anything else triggers a resync request.
        if last is not None and seq != last + 1 and seq != last:
            logger.warning(
                "Sequence gap on %s: last=%s got=%s — requesting resync",
                asset,
                last,
                seq,
            )
            if self._on_resync is not None:
                try:
                    await self._on_resync(asset, last, seq)
                except Exception as exc:  # noqa: BLE001 — caller resync best-effort
                    logger.error("Operation failed: error_type=%s", type(exc).__name__)
        self._last_seq[asset] = seq

    # ── connection lifecycle ───────────────────────────────────────────
    async def _subscribe(self, ws: Any) -> None:
        sub = {"type": "market", "assets_ids": self.config.asset_ids}
        await ws.send(json.dumps(sub))
        logger.info("Subscribed to market channel: %s", self.config.asset_ids)

    async def _watchdog(self, ws: Any) -> None:
        """Force-close the socket if no message arrives within the timeout.

        This is what catches a *silent freeze*: the TCP connection is alive but
        the venue stopped pushing. ``recv()`` would block forever; the watchdog
        closes the socket so the outer loop reconnects.
        """
        while not self._stop.is_set():
            await asyncio.sleep(self.config.ping_interval)
            idle = time.monotonic() - self._last_msg_ts
            if idle > self.config.heartbeat_timeout:
                logger.warning(
                    "Heartbeat timeout (%.1fs idle > %.1fs) — forcing reconnect",
                    idle,
                    self.config.heartbeat_timeout,
                )
                try:
                    await ws.close(code=4000, reason="heartbeat timeout")
                except Exception:  # noqa: BLE001 — closing a frozen socket may error
                    logger.debug("WebSocket close failed during heartbeat timeout")
                return
            try:
                await ws.ping()
            except Exception:  # noqa: BLE001 — ping failure ⇒ let recv loop error
                return

    async def _consume(self, ws: Any) -> None:
        self._last_msg_ts = time.monotonic()
        watchdog = asyncio.create_task(self._watchdog(ws))
        try:
            async for raw in ws:
                self._last_msg_ts = time.monotonic()
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logger.debug("non-JSON ws frame ignored")
                    continue
                messages = data if isinstance(data, list) else [data]
                for msg in messages:
                    if not isinstance(msg, dict):
                        continue
                    await self._check_gap(msg)
                    await self._on_message(msg)
        finally:
            watchdog.cancel()

    async def run(self) -> None:
        """Connect + consume forever with exponential-backoff reconnect."""
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "websockets not installed. pip install emerald-exchange[prediction_markets]"
            ) from exc

        backoff = self.config.backoff_base
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self.config.url,
                    ping_interval=None,  # we drive our own watchdog ping
                    close_timeout=5,
                ) as ws:
                    self._connected = True
                    self._reconnects = 0
                    backoff = self.config.backoff_base
                    await self._subscribe(ws)
                    await self._consume(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — reconnect on any error
                logger.warning("Operation failed: error_type=%s", type(exc).__name__)
            finally:
                self._connected = False

            if self._stop.is_set():
                break

            self._reconnects += 1
            if (
                self.config.max_reconnects
                and self._reconnects > self.config.max_reconnects
            ):
                logger.error(
                    "Max reconnects (%d) exceeded — giving up",
                    self.config.max_reconnects,
                )
                break

            # Exponential backoff with full jitter.
            import random

            sleep_for = min(backoff, self.config.backoff_max)
            sleep_for = random.uniform(0, sleep_for)  # nosec B311 — jitter, not crypto
            logger.info(
                "Reconnecting in %.2fs (attempt %d)", sleep_for, self._reconnects
            )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, self.config.backoff_max)
