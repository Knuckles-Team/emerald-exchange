---
name: emerald-exchange-account-intake
skill_type: skill
description: >-
  Take in account data: snapshot the Alpaca account with its positions
  (`emerald_exchange_get_account_snapshot`), read positions with stable identities
  (`emerald_exchange_get_account_positions`), and turn a statement CSV into validated activity records
  (`emerald_exchange_get_csv_activities`). Use when the agent must record balances and positions, reconcile a
  broker statement, or prepare activity for ingestion. Do NOT use for quotes and history (use
  emerald-exchange-market-data) or for order actions (use emerald-exchange-order-execution).
license: MIT
tags: [emerald-exchange, account, positions, statements, csv]
metadata:
  author: Knuckles-Team
  version: '0.2.0'
---
# Emerald Exchange Account Intake

## When to use
- Snapshot the active Alpaca account with equity, cash, buying power and positions.
- Read positions with a stable `position_id` (hash of account id and symbol).
- Import a broker statement given as CSV text with a column mapping.

## When NOT to use
- Plain account or position reads on any backend: `emerald-exchange-market-data`.
- Order actions: `emerald-exchange-order-execution`.

## Prerequisites & environment
Connect to the **`emerald-exchange`** MCP server. The active backend and mode come from the trading
configuration and default to the paper backend, which needs no credentials. Alpaca reads need the Alpaca
credentials in the operator configuration; provider reads need their provider key. Every tool here is
read-only and typed; there is no `action` argument. Never print a key.

## Tools
| Tool | Key arguments | Returns |
|---|---|---|
| `emerald_exchange_get_account_snapshot` | none | one record: the account fields plus `positions` |
| `emerald_exchange_get_account_positions` | none | positions with `account_id` and `position_id` |
| `emerald_exchange_get_csv_activities` | `content`, `mapping`, `tenant_id`, `instrument_id`, `license_tag`, `mode` | `records` with `record_id`, `checkpoint` |

## Procedure
1. Check the backend is Alpaca and the account has an identity (`emerald_exchange_get_account`).
2. Snapshot, then read positions; the symbols must be unique.
3. For a statement, confirm the column mapping with the owner, then import; report accepted and rejected rows.

## Gotchas
- Duplicate or empty position symbols are refused.
- An invalid statement is refused with a generic error; fix the mapping rather than retrying.
- `tenant_id`, `instrument_id` and `license_tag` are all required.
