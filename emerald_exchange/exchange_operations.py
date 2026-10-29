"""The exchange operations served as per-operation MCP tools: reads only.

Placing, modifying or cancelling orders (and connect/disconnect) changes
exchange state, so those go only through the risk-guarded
``emerald_orders_*`` tools (``mcp/mcp_orders.py``), which check RiskGuard
limits, halts and live-mode approval first. Serving the backend class
directly would have exposed ``submit_order``/``cancel_order`` as unguarded
per-operation tools, a way around the guard.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from typing import Any, Literal, cast
from uuid import uuid4

from emerald_exchange.backends import (
    BACKEND_REGISTRY,
    OHLCV,
    AccountInfo,
    AlpacaBackend,
    CCXTBackend,
    ExchangeBackend,
    ExecutionResult,
    Position,
    Quote,
)

#: Backend methods that may be served without the risk guard.
READ_OPERATIONS = (
    "get_quote",
    "get_historical",
    "get_positions",
    "get_account",
    "get_account_snapshot",
    "get_account_positions",
    "get_csv_activities",
    "get_stock_bars",
    "get_stock_quote",
    "get_stock_news",
    "get_stock_dividends",
    "get_company_records",
    "get_multi_asset_records",
    "get_exchange_history",
    "get_order_status",
    "exchanges",
)


class ExchangeReadOperations:
    """Read-only exchange operations over the configured backend."""

    def __init__(self, backend: ExchangeBackend) -> None:
        self._backend = backend

    def get_quote(self, symbol: str) -> Quote:
        """Latest quote for one symbol."""
        return self._backend.get_quote(symbol)

    def get_historical(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> list[OHLCV]:
        """Historical OHLCV bars for one symbol."""
        return self._backend.get_historical(symbol, period=period, interval=interval)

    def get_exchange_history(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str,
        license_tag: str,
        mode: Literal["delta"],
        limit: int = 1000,
        page_token: str | None = None,
        since: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Read one bounded CCXT candle page with stable exchange identity."""
        if not self._backend.name.startswith("ccxt:") or mode != "delta":
            raise ValueError("exchange history requires CCXT and delta mode")
        return cast(CCXTBackend, self._backend).get_history_page(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            license_tag=license_tag,
            limit=limit,
            page_token=page_token,
        )

    def get_positions(self) -> list[Position]:
        """Open positions."""
        return self._backend.get_positions()

    def get_account(self) -> AccountInfo:
        """Account balances and buying power."""
        return self._backend.get_account()

    def get_account_snapshot(self) -> list[dict[str, Any]]:
        """Read one Alpaca account and its positions as an ingestible record."""
        if self._backend.name != "alpaca":
            raise ValueError("account snapshot source requires the Alpaca backend")
        account = self._backend.get_account()
        if not account.account_id:
            raise ValueError("account snapshot source requires an account identity")
        positions = self._backend.get_positions()
        return [{**asdict(account), "positions": [asdict(item) for item in positions]}]

    def get_account_positions(self) -> list[dict[str, Any]]:
        """Read positions with stable identities scoped to their Alpaca account."""
        snapshot = self.get_account_snapshot()[0]
        account_id = snapshot["account_id"]
        symbols = [position["symbol"] for position in snapshot["positions"]]
        if any(not isinstance(symbol, str) or not symbol.strip() for symbol in symbols):
            raise ValueError("Alpaca position symbol is required")
        if len(symbols) != len(set(symbols)):
            raise ValueError("Alpaca position symbols must be unique")
        return [
            {
                **position,
                "account_id": account_id,
                "position_id": hashlib.sha256(
                    json.dumps([account_id, position["symbol"]]).encode()
                ).hexdigest(),
            }
            for position in snapshot["positions"]
        ]

    def get_stock_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str,
        adjustment: str,
        feed: str,
        license_tag: str,
        mode: Literal["delta"],
        limit: int = 1000,
        page_token: str | None = None,
        since: dict[str, Any] | None = None,
        session_scope: Literal["feed_native", "alpaca_calendar"] = "feed_native",
    ) -> dict[str, Any]:
        """Read one Alpaca page with explicit adjustment and feed labels."""
        if self._backend.name != "alpaca":
            raise ValueError("stock-bars source requires the Alpaca backend")
        if mode != "delta":
            raise ValueError("stock-bars source requires delta mode")
        return cast(AlpacaBackend, self._backend).get_stock_bars_page(
            symbol=symbol,
            start=start,
            end=end,
            timeframe=timeframe,
            adjustment=adjustment,
            feed=feed,
            license_tag=license_tag,
            limit=limit,
            page_token=page_token,
            session_scope=session_scope,
        )

    def get_stock_quote(
        self,
        symbol: str,
        feed: str,
        license_tag: str,
        mode: Literal["delta"],
        since: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Read an Alpaca quote with explicit feed and source time."""
        if self._backend.name != "alpaca":
            raise ValueError("stock-quote source requires the Alpaca backend")
        if mode != "delta":
            raise ValueError("stock-quote source requires delta mode")
        return cast(AlpacaBackend, self._backend).get_stock_quote(
            symbol=symbol, feed=feed, license_tag=license_tag
        )

    def get_stock_news(
        self,
        symbol: str,
        start: str,
        end: str,
        license_tag: str,
        mode: Literal["delta"],
        limit: int = 50,
        page_token: str | None = None,
        since: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Read one bounded page of Alpaca news headlines."""
        if self._backend.name != "alpaca" or mode != "delta":
            raise ValueError("stock-news source requires Alpaca and delta mode")
        return cast(AlpacaBackend, self._backend).get_stock_news_page(
            symbol=symbol,
            start=start,
            end=end,
            license_tag=license_tag,
            limit=limit,
            page_token=page_token,
        )

    def get_multi_asset_records(
        self,
        kind: Literal["fx", "commodity", "commodity_spot", "real_estate"],
        tenant_id: str,
        source_id: str,
        license_tag: str,
        mode: Literal["delta"],
        base: str = "",
        quote: str = "",
        dataset: str = "",
        symbol: str = "",
        start: str = "",
        end: str = "",
        attom_id: int = 0,
        max_age_days: int = 0,
        since: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Read bounded multi-asset provider observations."""
        from httpx import HTTPError

        from emerald_exchange.multi_asset_sources import (
            read_commodity,
            read_fx,
            read_gold_spot,
            read_valuation,
        )

        if mode != "delta":
            raise ValueError("multi-asset source requires delta mode")
        identity = {
            "tenant_id": tenant_id,
            "source_id": source_id,
            "license_tag": license_tag,
        }
        try:
            if kind == "fx":
                return read_fx(
                    os.environ.get("FMP_API_KEY", ""),
                    base=base,
                    quote=quote,
                    **identity,
                )
            if kind == "commodity":
                return read_commodity(
                    os.environ.get("DATABENTO_API_KEY", ""),
                    dataset=dataset,
                    symbol=symbol,
                    start=start,
                    end=end,
                    **identity,
                )
            if kind == "commodity_spot":
                return read_gold_spot(
                    os.environ.get("TWELVE_DATA_API_KEY", ""), **identity
                )
            if kind == "real_estate":
                return read_valuation(
                    os.environ.get("ATTOM_API_KEY", ""),
                    attom_id=attom_id,
                    max_age_days=max_age_days,
                    **identity,
                )
            raise ValueError("unsupported multi-asset kind")
        except (HTTPError, ValueError, TypeError, OverflowError, KeyError):
            raise RuntimeError("multi-asset provider read failed") from None

    def get_company_records(
        self,
        symbol: str,
        dataset: Literal["profile", "income", "earnings", "logo"],
        license_tag: str,
        mode: Literal["delta"],
        since: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Read a bounded FMP company dataset for an Alpaca symbol."""
        if self._backend.name != "alpaca" or mode != "delta":
            raise ValueError("company source requires Alpaca and delta mode")
        return cast(AlpacaBackend, self._backend).get_company_records(
            symbol=symbol,
            dataset=dataset,
            license_tag=license_tag,
        )

    def get_stock_dividends(
        self,
        symbol: str,
        start: str,
        end: str,
        license_tag: str,
        mode: Literal["delta"],
        limit: int = 100,
        page_token: str | None = None,
        since: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Read one bounded page of Alpaca corporate-action dividends."""
        if self._backend.name != "alpaca" or mode != "delta":
            raise ValueError("stock-dividends source requires Alpaca and delta mode")
        return cast(AlpacaBackend, self._backend).get_stock_dividends_page(
            symbol=symbol,
            start=start,
            end=end,
            license_tag=license_tag,
            limit=limit,
            page_token=page_token,
        )

    def get_csv_activities(
        self,
        content: str,
        mapping: dict[str, str],
        tenant_id: str,
        instrument_id: str,
        license_tag: str,
        mode: Literal["delta"],
        since: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Read validated statement rows for the active Alpaca account."""
        from agent_connector_sdk.finance.csv_import import (
            AccountContext,
            ColumnMapping,
            import_activities,
        )

        if self._backend.name != "alpaca":
            raise ValueError("CSV activity source requires the Alpaca backend")
        if mode != "delta":
            raise ValueError("CSV activity source requires delta mode")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (tenant_id, instrument_id, license_tag)
        ):
            raise ValueError(
                "CSV activity source requires tenant, instrument and license"
            )
        account = self._backend.get_account()
        if not account.account_id:
            raise ValueError("CSV activity source requires an account identity")
        context = AccountContext(
            tenant_id=tenant_id,
            source_id="alpaca-csv-activities",
            provider="alpaca",
            instrument_id=instrument_id,
            account_id=account.account_id,
            license_tag=license_tag,
        )
        try:
            activities = import_activities(
                content.encode(), ColumnMapping(mapping), context
            )
        except (ValueError, TypeError, OverflowError):
            raise ValueError("Invalid CSV activity statement") from None
        records = []
        for activity in activities:
            identity = json.dumps(
                [
                    tenant_id,
                    context.source_id,
                    context.provider,
                    account.account_id,
                    activity.source_event_id,
                ],
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode()
            records.append(
                {
                    **activity.model_dump(mode="json"),
                    "record_id": hashlib.sha256(identity).hexdigest(),
                }
            )
        return {"records": records, "checkpoint": {"generation": uuid4().hex}}

    def exchanges(self) -> dict[str, Any]:
        """Available exchange backends, the active backend and its mode."""
        return {
            "available": list(BACKEND_REGISTRY),
            "active": self._backend.name,
            "mode": self._backend.mode,
        }

    def get_order_status(self, order_id: str) -> ExecutionResult:
        """Status of one submitted order."""
        return self._backend.get_order_status(order_id)
