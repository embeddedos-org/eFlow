# SPDX-License-Identifier: MIT
"""Tests for the agent-facing validate-before-run CLI.

``python -m eflow validate <flow.json>`` (eflow/cli.py): exit 0 on a
valid flow, exit 2 with machine-readable ``{"ok": false, "errors": [...]}``
on stdout for any invalid flow, fail-closed on a missing file. The CLI
never executes the flow.
"""
import json
import subprocess
import sys
from pathlib import Path

from eflow.cli import EXIT_INVALID, EXIT_OK, main

REPO = Path(__file__).resolve().parent.parent
FLOWS = REPO / "eflow" / "flows"


def _flow_doc(nodes, edges):
    return {"flow": "t", "version": 1, "nodes": nodes, "edges": edges}


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def _run_cli(path, capsys):
    """Run the CLI in-process; return (exit code, stdout JSON, stderr)."""
    code = main(["validate", str(path)])
    out, err = capsys.readouterr()
    return code, json.loads(out), err


def test_valid_example_flow_passes(capsys):
    code, payload, _err = _run_cli(FLOWS / "fan_control.json", capsys)
    assert code == EXIT_OK == 0
    assert payload["ok"] is True
    assert payload["flow"] == "fan-control"
    assert payload["nodes"] == 5 and payload["edges"] == 4


def test_bad_port_type_fails(capsys, tmp_path):
    # logic.threshold emits bool; filter.moving_avg wants float.
    path = _write(tmp_path, "badport.json", _flow_doc(
        [{"id": "s", "type": "sensor.tmp117", "params": {}},
         {"id": "t", "type": "logic.threshold", "params": {"level": 1}},
         {"id": "f", "type": "filter.moving_avg", "params": {}}],
        [{"from": "s:out", "to": "t:in"},
         {"from": "t:out", "to": "f:in"}]))
    code, payload, _err = _run_cli(path, capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert payload["errors"], "errors must be machine-readable"
    assert any("type mismatch" in e for e in payload["errors"])


def test_cyclic_graph_fails(capsys, tmp_path):
    path = _write(tmp_path, "cycle.json", _flow_doc(
        [{"id": "a", "type": "filter.moving_avg", "params": {}},
         {"id": "b", "type": "filter.moving_avg", "params": {}}],
        [{"from": "a:out", "to": "b:in"},
         {"from": "b:out", "to": "a:in"}]))
    code, payload, _err = _run_cli(path, capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert any("cycle" in e for e in payload["errors"])


def test_missing_file_fails_closed(capsys, tmp_path):
    code, payload, _err = _run_cli(tmp_path / "does-not-exist.json", capsys)
    assert code != 0
    assert payload["ok"] is False
    assert any("cannot read" in e for e in payload["errors"])


def test_invalid_json_fails(capsys, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    code, payload, _err = _run_cli(path, capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert any("invalid JSON" in e for e in payload["errors"])


def test_schema_structure_failure_fails(capsys, tmp_path):
    # missing required key 'flow' -> structural layer, before the interpreter
    path = _write(tmp_path, "nosuch.json",
                  {"version": 1, "nodes": [], "edges": []})
    code, payload, _err = _run_cli(path, capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert any("missing required key" in e for e in payload["errors"])


def test_unknown_node_type_fails_semantic(capsys, tmp_path):
    path = _write(tmp_path, "unknown.json", _flow_doc(
        [{"id": "a", "type": "nope.x", "params": {}}], []))
    code, payload, _err = _run_cli(path, capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert any("unknown type" in e for e in payload["errors"])


def test_module_entrypoint_works():
    # python -m eflow validate must behave like the CLI contract
    r = subprocess.run(
        [sys.executable, "-m", "eflow", "validate",
         str(FLOWS / "fan_control.json")],
        cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0
    assert json.loads(r.stdout)["ok"] is True

    r = subprocess.run(
        [sys.executable, "-m", "eflow", "validate",
         str(FLOWS / "no-such-flow.json")],
        cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 2
    assert json.loads(r.stdout)["ok"] is False
