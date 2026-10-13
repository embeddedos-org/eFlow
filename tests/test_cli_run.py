# SPDX-License-Identifier: MIT
"""Tests for the eFlow `run` subcommand.

``python -m eflow run <flow.json>`` runs the exact validate pipeline
first; on any validation error it exits 2 with the same machine-readable
shape as ``validate`` and executes nothing. On success it executes via
the interpreter and prints the result as JSON.
"""
import json
import subprocess
import sys
from pathlib import Path

from eflow.cli import EXIT_INVALID, EXIT_OK, main

REPO = Path(__file__).resolve().parent.parent
FLOWS = REPO / "eflow" / "flows"


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def _run_cli(path, capsys, *extra):
    code = main(["run", str(path), *extra])
    out, err = capsys.readouterr()
    return code, json.loads(out), err


def test_valid_example_flow_runs(capsys):
    code, payload, _err = _run_cli(FLOWS / "fan_control.json", capsys)
    assert code == EXIT_OK == 0
    assert payload["ok"] is True
    assert payload["flow"] == "fan-control"
    result = payload["result"]
    # fan_control sinks: debug.console + gpio_led, one entry per tick.
    assert len(result["console"]) == payload["ticks"] == 20
    assert len(result["gpio_led"]) == 20
    assert all(isinstance(v, float) for v in result["console"])


def test_run_respects_ticks(capsys):
    code, payload, _err = _run_cli(
        FLOWS / "fan_control.json", capsys, "--ticks", "3")
    assert code == EXIT_OK
    assert payload["ticks"] == 3
    assert len(payload["result"]["console"]) == 3


def test_invalid_flow_exits_2_with_no_execution(capsys, tmp_path):
    # A cyclic flow: if it were executed it could never be a DAG run;
    # the contract is exit 2, machine-readable errors, and no result.
    path = _write(tmp_path, "cycle.json", {
        "flow": "t", "version": 1,
        "nodes": [{"id": "a", "type": "filter.moving_avg", "params": {}},
                  {"id": "b", "type": "filter.moving_avg", "params": {}}],
        "edges": [{"from": "a:out", "to": "b:in"},
                  {"from": "b:out", "to": "a:in"}]})
    code, payload, _err = _run_cli(path, capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert any("cycle" in e for e in payload["errors"])
    assert "result" not in payload


def test_missing_file_fails_closed(capsys, tmp_path):
    code, payload, _err = _run_cli(tmp_path / "does-not-exist.json", capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert "result" not in payload


def test_invalid_json_fails_closed(capsys, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    code, payload, _err = _run_cli(path, capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert "result" not in payload


def test_module_entrypoint_run_works():
    r = subprocess.run(
        [sys.executable, "-m", "eflow", "run",
         str(FLOWS / "fan_control.json")],
        cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0
    assert json.loads(r.stdout)["ok"] is True

    r = subprocess.run(
        [sys.executable, "-m", "eflow", "run",
         str(FLOWS / "no-such-flow.json")],
        cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 2
    assert json.loads(r.stdout)["ok"] is False
