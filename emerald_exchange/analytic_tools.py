"""Serve the hand-written analytic tools one typed tool per action.

scion-sdk 0.3.0 drops every registrar tool that routes on an
``action`` argument once per-operation client tools are registered, which
silently removed emerald's computed tools (signals, risk, market making,
strategy, statarb, derivatives, crypto, debate, fundamentals, wallet intel,
prediction markets and the risk-guarded order path). These are analyses, not
exchange API operations, so they are not covered by the backend's
per-operation tools.

Each registrar runs against a scratch server; every action it implements
becomes ``<tool>_<action>`` with the registrar's own typed parameters (minus
``action``), so no tool takes ``action`` or an untyped ``params_json``.
"""

from __future__ import annotations

import inspect
import re
import sys
import typing
from collections.abc import Callable, Iterable
from typing import Any

from fastmcp import FastMCP
from scion_sdk.config import setting
from scion_sdk.mcp.tool_surface import registered_tools

#: Actions that only read or compute; everything else may change state.
_READ_ONLY = re.compile(
    r"^(list|get|status|check|limits|regime|alpha|fuse|surveillance|insider|"
    r"kelly|bayesian|empirical|drawdown|daily|quote|fee|backtest|validate|pbo|"
    r"forensic|brier|ou_|dynamic|implied|smile|calibrate|vol_|funding|whale|"
    r"on_chain|arb|cointegration|consensus|history|filings|financials|risk_factors|"
    r"mdna|full_text|standardize|rank|wallet|smart|exit|fetch|evaluate|export|"
    r"positions|account|exchanges|historical)"
)
_DESTRUCTIVE = re.compile(r"^(cancel|halt)")
_COMPARE = re.compile(r"""action\s*==\s*["']([a-z][a-z0-9_]*)["']""")
_DOC_ITEM = re.compile(r"^\s*-\s*'([a-z][a-z0-9_]*)'", re.MULTILINE)


def tool_actions(tool: Any) -> list[str]:
    """Actions a tool implements: its ``action == "..."`` branches and doc list."""
    fn = inspect.unwrap(tool.fn)
    module = sys.modules.get(getattr(fn, "__module__", ""), None)
    source = inspect.getsource(module) if module is not None else ""
    seen: list[str] = []
    for name in [*_COMPARE.findall(source), *_DOC_ITEM.findall(fn.__doc__ or "")]:
        if name not in seen:
            seen.append(name)
    return seen


def _annotations(action: str) -> dict[str, Any]:
    destructive = bool(_DESTRUCTIVE.match(action))
    read_only = bool(_READ_ONLY.match(action)) and not destructive
    return {
        "title": action.replace("_", " ").title(),
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "idempotentHint": read_only,
        "openWorldHint": True,
    }


def _per_action(tool: Any, action: str) -> Callable[..., Any]:
    fn = tool.fn
    signature = inspect.signature(fn)
    hints = typing.get_type_hints(fn, include_extras=True)
    parameters = [
        p.replace(annotation=hints.get(p.name, p.annotation))
        for p in signature.parameters.values()
        if p.name != "action"
    ]

    async def call(**kwargs: Any) -> Any:
        result = fn(action=action, **kwargs)
        return await result if inspect.isawaitable(result) else result

    call.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters,
        return_annotation=hints.get("return", signature.return_annotation),
    )
    call.__annotations__ = {k: v for k, v in hints.items() if k != "action"}
    call.__name__ = action
    call.__doc__ = fn.__doc__
    return call


def serve_analytic_actions(
    mcp: Any,
    registry: Iterable[tuple[str, str, Callable[[Any], Any]]],
    *,
    rename: dict[str, str] | None = None,
) -> list[str]:
    """Run each enabled ``(tag, toggle, registrar)``; serve its tools per action.

    ``rename`` maps a registrar tool name to the prefix its per-action tools use.
    Returns the names registered.
    """
    scratch = FastMCP("emerald-analytics")
    for _tag, toggle, registrar in registry:
        if setting(toggle, True):
            registrar(scratch)
    served: list[str] = []
    for name, tool in registered_tools(scratch).items():
        if "action" not in (tool.parameters or {}).get("properties", {}):
            mcp.add_tool(tool)
            served.append(name)
            continue
        prefix = (rename or {}).get(name, name)
        for action in tool_actions(tool):
            tool_name = f"{prefix}_{action}"
            mcp.tool(
                name=tool_name,
                description=f"{action.replace('_', ' ').capitalize()} ({name}). "
                + (tool.description or ""),
                tags=set(tool.tags or set()) | {"analytic"},
                annotations=_annotations(action),
            )(_per_action(tool, action))
            served.append(tool_name)
    return served
