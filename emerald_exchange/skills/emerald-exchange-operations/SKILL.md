---
name: emerald-exchange-operations
skill_type: skill
description: >-
  Operate emerald-exchange through its governed MCP and Arbora capabilities, including emerald exchange kg ingestion, emerald exchange market data, emerald exchange order execution. Use when a request requires this provider's read, change, automation, ingestion, troubleshooting, or evidence workflows.
---

# Emerald Exchange Operations

Use the provider's governed MCP tools through Arbora delegation.

## Workflow

1. Establish the verified GraphSession and tenant before discovery or retrieval.
2. Discover the current condensed tool surface; never assume a stale tool name or schema.
3. Prefer read-only inspection first. For changes, present impact and use the provider's
   dry-run or preview mode when available.
4. Execute mutations as fenced WorkItems so retries remain idempotent and auditable.
5. Ingest source data only through the signed connector preset and ChangeEnvelope path.
6. Verify the durable result and its trace/evidence before reporting completion.

## Steps

1. Probe the tool surface with `emerald_market_data` `{"action": "exchanges"}`. Verify it returns the active backend and mode instead of an error.
2. Inspect before changing, using `emerald_portfolio` `{"action": "positions"}`. Verify the current holdings are recorded before any change.
3. For an order change, state the impact and use `emerald_orders` `{"action": "submit", "symbol": "<symbol>", "qty": 1}` only after the requester approves. Verify the response has `approved: true`.
4. For persistence use `emerald_ingest_snapshot` with `{}`. Verify the response has a non-null `ingested` count.
5. Re-read with `emerald_orders` `{"action": "status", "order_id": "<order_id>"}` and report ids. Verify the stored status matches the request.

## Failure recovery

| Failure | Cause | Recovery |
|---------|-------|----------|
| Order response has `approved: false` | The risk guard rejected the order | Report the `reason`, and resubmit only with a smaller `qty` the requester approves |
| `ingested` is null | No medulla engine is reachable | Report nothing persisted and ask the operator to start the engine before calling `emerald_ingest_snapshot` again |
| Authentication error on a live backend | Exchange credentials unset | Report the missing variable, or use the paper backend by setting `trading.default_mode` to `paper` |

## Safety contract

- Never persist credentials, endpoints, raw personal identifiers, hostnames, or local paths.
- Resolve TLS trust and verification from environment/configuration; never hardcode bypasses.
- Treat unknown ACL, tenant, schema, or tool-contract state as a hard failure.
- Require explicit approval for destructive, externally visible, or irreversible actions.
- Keep runtime traces policy-scoped and privacy-sanitized.

## Specialized workflows

Read [the workflow catalog](references/catalog.md) only when the request needs a
provider-specific procedure, parameter map, script, or reference asset.
