# SPDX-License-Identifier: MIT
"""Tests for the eFlow CLI `run` subcommand (validate, then execute).

`python -m eflow run <flow.json>` runs the validate pipeline first: an
invalid flow exits 2 with the machine-readable error shape and executes
nothing; a valid flow executes via the interpreter and emits the sink
log as JSON on stdout.
"""
import json

from eflow.cli import EXIT_INVALID, EXIT_OK, main

import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
FLOWS = REPO / "eflow" / "flows"


def _run_cli(args, capsys):
    code = main(args)
    out, err = capsys.readouterr()
    return code, json.loads(out), err


def test_run_valid_example_flow_executes(capsys):
    code, payload, _err = _run_cli(
        ["run", str(FLOWS / "fan_control.json"), "--ticks", "3"], capsys)
    assert code == EXIT_OK == 0
    assert payload["ok"] is True
    assert payload["flow"] == "fan-control"
    assert payload["ticks"] == 3
    assert "log" in payload and payload["log"]


def test_run_invalid_flow_executes_nothing(capsys, tmp_path):
    doc = {"flow": "t", "version": 1,
           "nodes": [{"id": "s", "type": "sensor.tmp117", "params": {}},
                     {"id": "t", "type": "logic.threshold",
                      "params": {"level": 1}},
                     {"id": "f", "type": "filter.moving_avg", "params": {}}],
           "edges": [{"from": "s:out", "to": "t:in"},
                     {"from": "t:out", "to": "f:in"}]}
    p = tmp_path / "badport.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    code, payload, err = _run_cli(["run", str(p)], capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert payload["errors"]
    assert "log" not in payload  # nothing executed
    assert "nothing executed" in err


def test_run_missing_file_fails_closed(capsys, tmp_path):
    code, payload, _err = _run_cli(
        ["run", str(tmp_path / "ghost.json")], capsys)
    assert code == EXIT_INVALID == 2
    assert payload["ok"] is False
    assert payload["errors"]
