# SPDX-License-Identifier: MIT
"""MCP tool surface for eFlow — `eflow_validate`.

The CLI (`eflow/cli.py`) already gives agents a validate-before-run
contract with a machine-readable verdict. This module exposes the
same validation as a proper MCP tool definition so an Agent-fabric
gateway can offer it alongside the org's other servers (see the
repo-root `server.json`):

- Input is the flow **document** (parsed JSON), never a host path —
  an MCP server must not read arbitrary files on behalf of a caller.
- The handler runs `eflow.cli.validate_document` — structural rules
  plus the interpreter's semantic load — and returns the CLI's
  verdict shape. It **validates only**: nothing is executed, ever.
  Running a flow stays with `python -m eflow run` after a human or
  agent has seen `ok: true`.
- Fail-closed: a non-object document or a malformed argument returns
  `{"ok": false, "errors": [...]}` rather than raising.
"""

from __future__ import annotations

from typing import Any, Dict

from .cli import validate_document

TOOL_DEFINITION: Dict[str, Any] = {
    "name": "eflow_validate",
    "description": (
        "Validate an eFlow flow document (structural schema rules plus "
        "semantic load: node types, port directions/types, unconnected "
        "inputs, acyclicity) WITHOUT executing it. Returns the same "
        "verdict shape as `python -m eflow validate`: "
        "{ok, errors, warnings, nodes, edges}."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "flow": {
                "type": "object",
                "description": "The flow document (parsed JSON), as in eflow/flows/*.json.",
            }
        },
        "required": ["flow"],
    },
    "annotations": {"readOnlyHint": True},
}


def eflow_validate(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle one `eflow_validate` call. Never raises, never executes."""
    if not isinstance(arguments, dict) or "flow" not in arguments:
        return {"ok": False,
                "errors": ["arguments must be an object with a 'flow' key"],
                "warnings": []}
    flow = arguments["flow"]
    if not isinstance(flow, dict):
        return {"ok": False,
                "errors": ["'flow' must be a flow document (JSON object)"],
                "warnings": []}
    errors, warns, nnodes, nedges = validate_document(flow)
    if errors:
        return {"ok": False, "errors": errors, "warnings": warns}
    return {"ok": True, "flow": flow.get("flow"), "nodes": nnodes,
            "edges": nedges, "warnings": warns}
