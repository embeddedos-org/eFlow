# SPDX-License-Identifier: MIT
"""Tests for the eflow_validate MCP tool definition + handler.

The handler must return the CLI's verdict shape, must fail closed on
malformed arguments, and must never execute a flow (validation only —
there is deliberately no path from this module to run_flow).
"""
import json
from pathlib import Path

from eflow.mcp_tools import TOOL_DEFINITION, eflow_validate

REPO = Path(__file__).resolve().parent.parent
FLOWS = REPO / "eflow" / "flows"


def _fan_control():
    return json.loads((FLOWS / "fan_control.json").read_text(encoding="utf-8"))


def test_tool_definition_shape():
    assert TOOL_DEFINITION["name"] == "eflow_validate"
    schema = TOOL_DEFINITION["inputSchema"]
    assert schema["type"] == "object"
    assert schema["required"] == ["flow"]
    # Validation is read-only; agents and gateways rely on the hint.
    assert TOOL_DEFINITION["annotations"]["readOnlyHint"] is True


def test_valid_flow_document_passes():
    verdict = eflow_validate({"flow": _fan_control()})
    assert verdict["ok"] is True
    assert verdict["flow"] == "fan-control"
    assert verdict["nodes"] == 5 and verdict["edges"] == 4


def test_invalid_flow_document_fails_with_errors():
    doc = {"flow": "t", "version": 1,
           "nodes": [{"id": "s", "type": "sensor.tmp117", "params": {}},
                     {"id": "t", "type": "logic.threshold", "params": {"level": 1}},
                     {"id": "f", "type": "filter.moving_avg", "params": {}}],
           "edges": [{"from": "s:value", "to": "t:in"},
                     {"from": "t:out", "to": "f:in"}]}
    verdict = eflow_validate({"flow": doc})
    assert verdict["ok"] is False
    assert verdict["errors"]


def test_malformed_arguments_fail_closed():
    assert eflow_validate({})["ok"] is False
    assert eflow_validate({"flow": "not-a-document"})["ok"] is False
    assert eflow_validate({"flow": [1, 2, 3]})["ok"] is False
