---
name: eflow-validate
description: Validate an eFlow dataflow JSON file before running or emitting it. Use when an agent needs to check a flow against the eFlow JSON Schema and the interpreter's semantic rules (node types, port types, acyclicity) — e.g. before emitting a generated flow, accepting a flow from another agent, or running a flow through the interpreter or target codegen.
---

# eFlow Validate-Before-Run

Agent-driven validation of eFlow dataflow documents via
`python -m eflow validate <flow.json>` (implemented in `eflow/cli.py`).
A flow is a JSON document with `nodes` and `edges`; validating it is
cheap, read-only, and never executes anything. Emitting or running an
unvalidated flow is how broken graphs reach devices.

## Quick start

```bash
# From the eFlow repo root
python -m eflow validate eflow/flows/fan_control.json

# Machine-readable verdict on stdout (exit 0 = valid)
python -m eflow validate my-flow.json | python3 -c "import json,sys; print(json.load(sys.stdin)['ok'])"
```

Success (exit 0):

```json
{"ok": true, "path": "...", "flow": "fan-control", "nodes": 5, "edges": 4, "warnings": []}
```

Failure (exit 2) — always machine-readable on stdout:

```json
{"ok": false, "path": "...", "errors": ["edge 't:out' -> 'f:in': type mismatch (bool -> float)"], "warnings": []}
```

## What it answers

- **Is this flow structurally sound?** — required keys, node-id/type
  shapes, `<node-id>:<port>` edge refs, no extra keys (the rules from
  `schema/eflow-flow.schema.json`, checked dependency-free).
- **Is it semantically loadable?** — runs the interpreter's `load()`
  without executing: known node types, port directions, port-type
  compatibility (int↔float allowed, bool→float rejected), every input
  port driven, and acyclicity with the cycle path in the error.
- **Is the file even usable?** — missing files and invalid JSON are
  fail-closed (exit 2, error on stdout), never guessed at.

`warnings` surfaces non-fatal weakening, e.g. an `any` port on an edge.
See `references/flow-format.md` for the full contract.

## Discipline

1. **Validate before run.** Every flow an agent emits, edits, or
   receives gets `python -m eflow validate` before it is run, committed,
   or handed to codegen. No exceptions.
2. **Fail closed.** Exit 2 means the flow is unusable: report the
   `errors` list, do not run the flow, do not repair it by guessing.
   Ask or fix the source document.
3. **Read-only.** Validation never executes the graph — no simulation,
   no side effects. `python -m eflow.interpreter` is the separate
   execution surface.
4. **Trust stdout, not stderr.** The JSON verdict is the contract; the
   stderr line is a human courtesy. Parse stdout.
5. **Pin the interpreter.** This skill validates against the registry
   in `eflow/interpreter.py` at the repo's current HEAD; new node types
   are reviewed changes, not assumptions.

## The MCP tool: `eflow_validate`

The same validation is exposed as an MCP tool
(`eflow/mcp_tools.py`, registered in the repo-root `server.json`),
for agents working through the Agent fabric's gateway rather than
a shell. The contract is identical; only the input shape differs:

- **Input is the flow document, never a path.** The tool takes
  `{"flow": { ... }}` — the parsed JSON object. An MCP server must
  not read arbitrary host files on a caller's behalf, so there is
  no filename argument; read the file yourself and pass its
  contents.
- **Output is the CLI verdict, minus `path`:**
  `{"ok": bool, "errors": [...], "warnings": [...]}` on failure,
  plus `"flow"`, `"nodes"`, and `"edges"` on success. Parse it
  exactly as you would the CLI's stdout.
- **Read-only by construction.** The tool is annotated
  `readOnlyHint`; the handler calls `validate_document` only and
  does not import the interpreter's execution surface. Validation
  through the tool never runs the flow — the same discipline as
  the CLI, enforced in code.
- **Fail-closed.** A non-object `flow` returns
  `{"ok": false, "errors": ["flow must be a JSON object"], ...}`
  rather than raising, and an unknown tool name through the
  module's `call_tool` dispatcher returns a structured error.

Prefer the tool when a gateway session is already open; prefer
the CLI when you are already in a shell with the file on disk.
Either way: validate before run, and treat `ok: false` as final
until the document — not the verdict — changes.
