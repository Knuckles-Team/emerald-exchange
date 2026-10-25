# CONN-EMERALD-EXCHANGE-XRPL — XRPL agent wallet, payments and trading

Owner: emerald-exchange. Cross-repo IDs: none.

## Purpose and user stories

An agent runs a wallet on the XRPL network. It moves XRP and RLUSD, escrows funds for gated work, trades on the native DEX, and answers account and portfolio queries. Every agent-initiated transaction carries attribution, passes the spending-limit check, and previews before it signs. The wallet defaults to the test network; production needs an explicit opt-in.

## Requirements and acceptance

See [requirements.md](requirements.md) for the definition of every requirement ID this spec owns and [status.json](status.json) for their current delivery and acceptance state.

## Why a new spec

Search of `specs/`: `EMERALD-OPS` owns read-only exchange operations on the existing backends, `EMERALD-GUIDE` owns the leveraged trading guide, `EMERALD-MEDIA` owns finance media intake, and `CONN-EMERALD-EXCHANGE-CONNECTOR-CONTENT` owns the packaged content surface. None owns the XRPL network: its wallets, payments, trust lines, escrow, DEX, attribution, or risk controls. XRPL is a new external system for this connector, so the capability gets its own spec.

## Scope and interfaces

Owned: wallet create, load and sign; XRP and RLUSD payments; trust lines; escrow-gated work; native DEX and AMM market operations; account and portfolio queries; SourceTag and Memo attribution; spending limits and kill-switch; and the docs, network endpoint, fee schedule and live status resources. The MCP server serves these through the existing `emerald-exchange-mcp` connector surface, the existing skill and prompt packaging, and the ontology pack.

Non-goals: custody for other networks, a second payment stack, and any order path that bypasses the existing risk guard and execution bridge.

## Open questions

- None. Production opt-in is a future requirements row, not a silent default.
