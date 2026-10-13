# SPDX-License-Identifier: MIT
"""Agent-facing validate-before-run CLI for eFlow.

``python -m eflow run <flow.json>`` runs the exact validate pipeline
first (see below) and only executes a flow that validates; on any
validation error it exits 2 with the same machine-readable error
shape as ``validate`` and executes nothing.

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

from .interpreter import FLOW_VERSION, FlowError, load, run_flow

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


def _json_safe(value: Any) -> Any:
    """Recursively convert tuples (sink-log entries) to JSON-safe lists."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _read_flow(path: str):
    """Read + parse a flow file; returns (flow, error_payload_or_None)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or str(exc)
        return None, {"ok": False, "path": path,
                      "errors": [f"cannot read file: {reason}"],
                      "warnings": []}
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, {"ok": False, "path": path,
                      "errors": [f"invalid JSON: {exc}"], "warnings": []}


def run_command(path: str, ticks: int = 20) -> int:
    """Validate one flow file, then execute it. Returns 0 or 2.

    Runs the exact validate pipeline first (structural rules plus
    ``interpreter.load()`` via :func:`validate_document`); on any
    validation error, exits 2 with the same machine-readable shape as
    ``validate`` and executes nothing. On success, executes via the
    interpreter's ``run_flow`` entry point and prints the sink log as
    JSON on stdout.
    """
    flow, error_payload = _read_flow(path)
    if error_payload is not None:
        _emit(error_payload)
        print(f"eflow run: {error_payload['errors'][0]}", file=sys.stderr)
        return EXIT_INVALID
    errors, warns, _nnodes, _nedges = validate_document(flow)
    if errors:
        _emit({"ok": False, "path": path, "errors": errors,
               "warnings": warns})
        print(f"eflow run: {path} INVALID ({len(errors)} error(s)); "
              "nothing executed", file=sys.stderr)
        return EXIT_INVALID
    try:
        result = run_flow(flow, ticks=ticks)
    except Exception as exc:  # validated flow should not fail; fail closed
        _emit({"ok": False, "path": path,
               "errors": [f"execution failed: {exc}"], "warnings": warns})
        print(f"eflow run: execution failed for {path}: {exc}",
              file=sys.stderr)
        return EXIT_INVALID
    _emit({"ok": True, "path": path, "flow": flow.get("flow"),
           "ticks": ticks, "warnings": warns,
           "result": _json_safe(result)})
    return EXIT_OK


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="eflow",
        description="eFlow validate-before-run CLI")
    sub = ap.add_subparsers(dest="command", required=True)
    p_val = sub.add_parser("validate",
                           help="validate a flow JSON file (no execution)")
    p_val.add_argument("flow", help="path to the flow JSON file")
    p_run = sub.add_parser(
        "run", help="validate a flow JSON file, then execute it")
    p_run.add_argument("flow", help="path to the flow JSON file")
    p_run.add_argument("--ticks", type=int, default=20,
                       help="number of interpreter ticks to run (default: 20)")
    args = ap.parse_args(argv)
    if args.command == "validate":
        return validate_command(args.flow)
    if args.command == "run":
        return run_command(args.flow, ticks=args.ticks)
    return EXIT_INVALID  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())

