# CONN-EMERALD-EXCHANGE-XRPL — Design and implementation plan

Governing spec: [spec.md](spec.md).

## Existing system and reuse

`emerald_exchange/mcp/` serves the MCP surface under the `emerald-exchange-mcp` connector identity declared in `pyproject.toml`. `emerald_exchange/skills/` holds the skill packages, `emerald_exchange/prompts/` the prompts, and `emerald_exchange/ontology/` the TTL packs with `certification.json`. The existing risk guard, execution bridge and paper default carry over unchanged; XRPL joins them as a new backend, not a second path.

## Architecture

A new `emerald_exchange/` module owns the XRPL backend: wallet lifecycle, transaction build and ledger access. Wallet secrets stay behind an address reference. Signing runs preview, then scoped auto-sign or explicit approval, then submit. One attribution helper stamps SourceTag and Memo on every agent transaction. The spending-limit check and the kill-switch sit in the existing risk guard before any outbound call. The ledger client supplies fee schedules, network endpoints and live status to the resource surface.

## Interfaces and data model

MCP tools follow the existing per-operation pattern: `xrpl_wallet_*`, `xrpl_pay_*`, `xrpl_trust_*`, `xrpl_escrow_*`, `xrpl_dex_*`, `xrpl_account_*`. Each mutating tool returns a preview object carrying fee, destination, attribution and limit-check result before it signs. The resource surface adds docs, network endpoint, fee schedule and live status entries. The ontology content lands as a new XRPL TTL in `emerald_exchange/ontology/` under the existing certification.

## Live integration path

MCP tool call, XRPL backend, ledger client, signed transaction with SourceTag and Memo, ledger result. Read-only tools stop at the ledger query. No path bypasses the risk guard; the kill-switch check runs first.

## Quality and release gates

Repository pre-commit stage on changed files. `tests/test_public_specs.py` checks the spec contract. XRPL tests run against the test network or a local validator, never production.

## Risks, alternatives, and decisions

Decision: testnet default and preview-before-sign; production needs the explicit opt-in row and a dated Amendments entry. Risk: fee drift; the fee schedule resource refreshes live and the spending-limit check reads the same source. Alternative rejected: hosted signing; the key material would leave the connector boundary.

## Amendments

- None yet.
