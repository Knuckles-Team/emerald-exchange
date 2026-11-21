---
name: emerald-exchange-stock-reference
skill_type: skill
description: >-
  Read Alpaca stock reference data with explicit labels: a feed-labelled quote
  (`emerald_exchange_get_stock_quote`), a bounded page of bars with adjustment and feed
  (`emerald_exchange_get_stock_bars`), news headlines (`emerald_exchange_get_stock_news`), dividends
  (`emerald_exchange_get_stock_dividends`) and FMP company profile, income, earnings or logo records
  (`emerald_exchange_get_company_records`). Use when a result must state its feed, adjustment, license tag and
  page token. Do NOT use for a plain quote or bars on any backend (use emerald-exchange-market-data) or for
  FX, commodities and exchange candles (use emerald-exchange-multi-asset).
license: MIT
tags: [emerald-exchange, alpaca, stocks, news, dividends]
metadata:
  author: Knuckles-Team
  version: '0.2.0'
---
# Emerald Exchange Stock Reference

These tools need the Alpaca backend and `mode` set to `delta`. Each returns a bounded page and a checkpoint.

## When to use
- A stock quote whose feed and source time must be explicit.
- Bars with a stated `timeframe`, `adjustment`, `feed` and `session_scope`.
- News headlines or dividends of one symbol in a date window.
- Company profile, income, earnings or logo records.

## When NOT to use
- Plain quote or history on any backend: `emerald-exchange-market-data`.
- Exchange candles, FX, commodities, property: `emerald-exchange-multi-asset`.

## Prerequisites & environment
Connect to the **`emerald-exchange`** MCP server. The active backend and mode come from the trading
configuration and default to the paper backend, which needs no credentials. Alpaca reads need the Alpaca
credentials in the operator configuration; provider reads need their provider key. Every tool here is
read-only and typed; there is no `action` argument. Never print a key.

## Tools
| Tool | Key arguments | Returns |
|---|---|---|
| `emerald_exchange_get_stock_quote` | `symbol`, `feed`, `license_tag`, `mode` | `quotes`, `checkpoint` |
| `emerald_exchange_get_stock_bars` | `symbol`, `start`, `end`, `timeframe`, `adjustment`, `feed`, `license_tag`, `mode`, `limit`, `page_token`, `session_scope` | `bars`, `next_page_token`, `checkpoint` |
| `emerald_exchange_get_stock_news` | `symbol`, `start`, `end`, `license_tag`, `mode`, `limit`, `page_token` | `news`, `next_page_token`, `checkpoint` |
| `emerald_exchange_get_stock_dividends` | `symbol`, `start`, `end`, `license_tag`, `mode`, `limit`, `page_token` | `dividends`, `next_page_token`, `checkpoint` |
| `emerald_exchange_get_company_records` | `symbol`, `dataset` (`profile`, `income`, `earnings`, `logo`), `license_tag`, `mode` | `records`, `checkpoint` |

## Procedure
1. Check the backend with `emerald_exchange_exchanges`; these tools refuse any backend but Alpaca.
2. Fix `feed`, `adjustment` and `timeframe` for the whole series and keep them on every page.
3. Pass the returned `next_page_token` as `page_token` until it is empty.

## Gotchas
- `session_scope` is `feed_native` or `alpaca_calendar`; it changes which bars appear.
- `mode` other than `delta` is refused.
