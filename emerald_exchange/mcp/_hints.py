"""MCP tool annotations shared by the hand-written per-operation tools.

Each tool is one operation with its own typed parameters; these hints tell the
door that serves the connector whether a call reads, writes or destroys.
Destructive tools also run :func:`scion_sdk.mcp.destructive.guard_destructive`
before they act.
"""

from __future__ import annotations

import json
from typing import Any

from scion_sdk.mcp.destructive import guard_destructive

#: Reads or computes; the same arguments give the same answer.
READ: dict[str, Any] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
#: Records or changes state, but undoes nothing the caller cannot redo.
WRITE: dict[str, Any] = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}
#: Places, cancels or halts trading: asks the caller to confirm first.
DESTRUCTIVE: dict[str, Any] = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True,
}


async def refused_unless_confirmed(
    ctx: Any, operation: str, arguments: dict[str, Any], confirm: bool
) -> Any | None:
    """``None`` when the destructive call may proceed, else what to return.

    A plain refusal payload is returned as JSON text like every other tool
    result; an MCP input request is returned as is so the client can answer it.
    """
    refused = await guard_destructive(ctx, operation, arguments, confirm=confirm)
    if isinstance(refused, dict):
        return json.dumps(refused)
    return refused
