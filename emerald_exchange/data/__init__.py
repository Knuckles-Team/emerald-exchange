"""Market-data & fundamentals subpackage for emerald-exchange.

Folds two previously-standalone MCP servers into emerald-exchange as data
providers:

* :mod:`emerald_exchange.data.edgar` — SEC EDGAR filings/financials via the
  optional ``edgartools`` dependency (CONCEPT:EX-AHE.harness.ee-26).
* :mod:`emerald_exchange.data.wallet_intel` — Polymarket wallet analytics over a
  ``poly_data`` trade dataset (CONCEPT:EX-AHE.harness.ee-27).

Both keep their heavy/optional third-party deps (``edgartools`` / ``polars`` /
``py-clob-client``) lazily imported so importing emerald-exchange never hard-fails
when they are absent.
"""
