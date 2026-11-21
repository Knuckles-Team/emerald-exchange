---
name: emerald-exchange-performance-records
skill_type: skill
description: >-
  Write the stored records the return engine reads: the account's value as a valuation record
  (`emerald_exchange_get_account_valuation`) and a bounded page of index bars as benchmark-level records
  (`emerald_exchange_get_benchmark_levels`). Use when the agent must record account value over time or an index
  level to compare a return against. Do NOT use for a plain quote or bars (use emerald-exchange-market-data or
  emerald-exchange-stock-reference) or for the account snapshot and statement deposits and withdrawals (use
  emerald-exchange-account-intake).
license: MIT
tags: [emerald-exchange, performance, valuation, benchmark]
metadata:
  author: Knuckles-Team
  version: '0.1.0'
---
# Emerald Exchange Performance Records

Both tools need the Alpaca backend and `mode` set to `delta`, and both are read-only: they return records, and the
sink writes them. Money is a decimal string, never a float.

## When to use
- Record the active account's total value, cash included, at this instant.
- Record the closing level of an index tracker, one record per bar, under a benchmark name such as `SPX`.

## When NOT to use
- A balance or position read: `emerald-exchange-account-intake` or `emerald-exchange-market-data`.
- Bars you only want to look at, without a benchmark name: `emerald-exchange-stock-reference`.

## Prerequisites & environment
Connect to the **`emerald-exchange`** MCP server with the Alpaca backend active. A valuation record needs the
provider account identity and a tenant. A benchmark record needs a tenant, an identifier as the benchmark name and
a tracker symbol with an explicit feed, adjustment and license tag. Never print a key.

## Tools
| Tool | Key arguments | Returns |
|---|---|---|
| `emerald_exchange_get_account_valuation` | `tenant_id`, `mode`, `since` | `records` (one valuation record), `checkpoint` |
| `emerald_exchange_get_benchmark_levels` | `tenant_id`, `benchmark`, `symbol`, `start`, `end`, `timeframe`, `adjustment`, `feed`, `license_tag`, `mode`, `limit`, `page_token` | `records` (one per bar), `next_page_token`, `checkpoint` |

## Procedure
1. Check the backend is Alpaca (`emerald_exchange_exchanges`).
2. For a value, read the valuation once per instant; a second read at a later instant is a second record.
3. For a benchmark, page with `page_token` and carry the checkpoint forward; keep the feed and adjustment the same on every page.

## Gotchas
- A benchmark record belongs to no account and carries no currency.
- A non-positive index level, a blank tenant and a benchmark name that is not an identifier are refused.
- A non-finite account value is refused; no record is made up.
