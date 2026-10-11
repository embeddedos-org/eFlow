# SPDX-License-Identifier: MIT
"""Agent-facing validate-before-run CLI for eFlow.

``python -m eflow validate <flow.json>`` checks a flow document in two
layers and never executes it:

1. Structural — the rules from ``schema/eflow-flow.schema.json``,
   implemented dependency-free (CI installs only pytest, so the ``jsonschema``
   package is not available).
2. Semantic — ``eflow.interpreter.load()``: known node types, port
   directions, port-type compatibility, unconnected inputs, and acyclicity.

Machine-readable contract (this is the documented choice): the verdict
always goes to **stdout** as a single JSON object, so agents can pipe it.
Human-facing notes go to stderr. Exit codes:

- ``0`` — valid: ``{"ok": true, ...}``
- ``2`` — invalid or unreadable: ``{"ok": false, "errors": [...], ...}``

Missing files, invalid JSON, and schema/semantic violations are all
fail-closed: non-zero exit with an error list, never a guess.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .interpreter import FLOW_VERSION, FlowError, load

EXIT_OK = 0
EXIT_INVALID = 2

_NODE_TYPE_RE = re.compile(r"^[a-z]+\.[a-z0-9_]+$")
_PORT_REF_RE = re.compile(r"^[^:]+:[^:]+$")
_FLOW_KEYS = {"flow", "version", "nodes", "edges"}
_NODE_KEYS = {"id", "type", "params"}
_EDGE_KEYS = {"from", "to"}


def validate_structure(flow: Any) -> List[str]:
    """Structural rules from ``schema/eflow-flow.schema.json``.

    Dependency-free so the CLI works wherever the interpreter does.
    Returns the list of violations (empty when the shape is valid).
    """
    errors: List[str] = []
    if not isinstance(flow, dict):
        return ["flow document must be a JSON object"]
    extra = set(flow) - _FLOW_KEYS
    if extra:
        errors.append(f"unexpected top-level keys: {sorted(extra)}")
    for key in ("flow", "version", "nodes", "edges"):
        if key not in flow:
            errors.append(f"missing required key {key!r}")
    if "flow" in flow and not (isinstance(flow["flow"], str)
                               and flow["flow"]):
        errors.append("'flow' must be a non-empty string")
    if "version" in flow:
        version = flow["version"]
        if isinstance(version, bool) or version != FLOW_VERSION:
            errors.append(
                f"'version' must be {FLOW_VERSION}, got {version!r}")

    if "nodes" in flow:
        nodes = flow["nodes"]
        if not isinstance(nodes, list) or not nodes:
            errors.append("'nodes' must be a non-empty array")
        else:
            for i, n in enumerate(nodes):
                where = f"nodes[{i}]"
                if not isinstance(n, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                extra = set(n) - _NODE_KEYS
                if extra:
                    errors.append(f"{where}: unexpected keys {sorted(extra)}")
                nid = n.get("id")
                if not (isinstance(nid, str) and nid):
                    errors.append(f"{where}: 'id' must be a non-empty string")
                ntype = n.get("type", "")
                if not (isinstance(ntype, str)
                        and _NODE_TYPE_RE.match(ntype)):
                    errors.append(f"{where}: bad node type {ntype!r}")
                if "params" in n and not isinstance(n["params"], dict):
                    errors.append(f"{where}: 'params' must be an object")

    if "edges" in flow:
        edges = flow["edges"]
        if not isinstance(edges, list):
            errors.append("'edges' must be an array")
        else:
            for i, e in enumerate(edges):
                where = f"edges[{i}]"
                if not isinstance(e, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                extra = set(e) - _EDGE_KEYS
                if extra:
                    errors.append(f"{where}: unexpected keys {sorted(extra)}")
                for key in ("from", "to"):
                    ref = e.get(key, "")
                    if key not in e:
                        errors.append(f"{where}: missing required key {key!r}")
                    elif not (isinstance(ref, str)
                              and _PORT_REF_RE.match(ref)):
                        errors.append(
                            f"{where}: bad port ref {ref!r} "
                            "(want '<node-id>:<port>')")
    return errors


def validate_document(flow: Dict[str, Any]
                      ) -> Tuple[List[str], List[str], int, int]:
    """Both validation layers; returns (errors, warnings, nnodes, nedges)."""
    errors = validate_structure(flow)
    if errors:
        return errors, [], 0, 0
    with warnings.catch_warnings(record=True) as caught:
        # e.g. the 'any'-port weakening warning in interpreter.load()
        warnings.simplefilter("always")
        try:
            nodes, edges, _order = load(flow)
        except FlowError as exc:
            return ([str(exc)],
                    [str(w.message) for w in caught],
                    0, 0)
    return [], [str(w.message) for w in caught], len(nodes), len(edges)


def _emit(payload: Dict[str, Any]) -> None:
    # stdout is the machine-readable channel; agents parse this.
    print(json.dumps(payload, indent=2))


def validate_command(path: str) -> int:
    """Validate one flow file. Returns the process exit code (0 or 2)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or str(exc)
        _emit({"ok": False, "path": path,
               "errors": [f"cannot read file: {reason}"], "warnings": []})
        print(f"eflow validate: cannot read {path}: {reason}", file=sys.stderr)
        return EXIT_INVALID
    try:
        flow = json.loads(raw)
    except json.JSONDecodeError as exc:
        _emit({"ok": False, "path": path,
               "errors": [f"invalid JSON: {exc}"], "warnings": []})
        print(f"eflow validate: invalid JSON in {path}: {exc}",
              file=sys.stderr)
        return EXIT_INVALID

    errors, warns, nnodes, nedges = validate_document(flow)
    if errors:
        _emit({"ok": False, "path": path, "errors": errors,
               "warnings": warns})
        print(f"eflow validate: {path} INVALID "
              f"({len(errors)} error(s))", file=sys.stderr)
        return EXIT_INVALID
    _emit({"ok": True, "path": path, "flow": flow.get("flow"),
           "nodes": nnodes, "edges": nedges, "warnings": warns})
    if warns:
        print(f"eflow validate: {path} valid with "
              f"{len(warns)} warning(s)", file=sys.stderr)
    return EXIT_OK


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="eflow",
        description="eFlow validate-before-run CLI (validates, never runs)")
    sub = ap.add_subparsers(dest="command", required=True)
    p_val = sub.add_parser("validate",
                           help="validate a flow JSON file (no execution)")
    p_val.add_argument("flow", help="path to the flow JSON file")
    args = ap.parse_args(argv)
    if args.command == "validate":
        return validate_command(args.flow)
    return EXIT_INVALID  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
