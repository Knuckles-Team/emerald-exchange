# EMERALD-OPS — Design and architecture

`emerald_exchange/exchange_operations.py` defines `ExchangeReadOperations`, a read-only facade over the configured backend. `mcp_server.py` serves each public method as a per-operation tool through the shared tool-surface registrar (prefix `emerald`, so `exchanges` becomes `emerald_exchange_exchanges`). `READ_OPERATIONS` lists the methods allowed without the risk guard; a test fails if the facade grows a public method outside that list or a write operation. `exchanges` reads `BACKEND_REGISTRY` and the active backend's `name` and `mode`, and calls no exchange API.

For EMERALD-OPS-R003, the Alpaca backend obtains the account ID and currency from the provider. It validates numeric account and position values and refuses documented provider API or transport failures instead of inventing a zero account or an empty position list. The read facade exposes the account ID to the per-operation MCP tool. This path does not itself prove durable account ingestion or statement re-import.

EMERALD-OPS-R004 exposes a declared list of account snapshots over the same read facade. Each snapshot carries the account ID and its positions. The source refuses a non-Alpaca backend and fails if either provider read fails. The graph mapping and durable re-import proof are separate work.

## Multi-asset provider sources

Extend the read facade with bounded, non-authoritative provider source reads for
FX, commodity spot and specific futures prices, and dated property valuations.
Provider credentials come from the operator environment and never tool arguments.
Prices retain source time and instrument identity; a fixed futures contract has
an explicit no-roll policy and provider expiry. Property valuations retain the
provider date and report age against a caller-selected freshness threshold.
Synthetic provider fixtures establish transport behavior, not live entitlements.
