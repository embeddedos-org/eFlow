# SPDX-License-Identifier: MIT
"""Framing tests for the eFlow MCP stdio server (`eflow/mcp_server.py`).

Mirrors the EoSim client-harness style: drive `handle_message`
directly and run one end-to-end pass through `McpServer` over
StringIO. The server validates only — no test here can execute a
flow, because the server has no path to execution.
"""
import io
import json
from pathlib import Path

from eflow.mcp_server import McpServer, handle_message

REPO = Path(__file__).resolve().parent.parent
FLOWS = REPO / "eflow" / "flows"


def _temp_monitor():
    return json.loads((FLOWS / "temp_monitor.json").read_text(encoding="utf-8"))


def _call(msg_id, name, arguments):
    return handle_message(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


def _verdict(reply):
    return json.loads(reply["result"]["content"][0]["text"])


def test_initialize_handshake():
    reply = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    result = reply["result"]
    assert result["protocolVersion"] == "2026-07-28"
    assert result["serverInfo"] == {"name": "eflow-mcp", "version": "0.1.0"}
    assert result["capabilities"] == {"tools": {}}


def test_notification_gets_no_reply():
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_shows_eflow_validate():
    reply = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = reply["result"]["tools"]
    assert [t["name"] for t in tools] == ["eflow_validate"]
    assert tools[0]["annotations"]["readOnlyHint"] is True


def test_tools_call_valid_flow_validates():
    verdict = _verdict(_call(3, "eflow_validate", {"flow": _temp_monitor()}))
    assert verdict["ok"] is True
    assert verdict["flow"] == "temp-monitor"


def test_tools_call_invalid_flow_returns_structured_error():
    doc = {"flow": "t", "version": 1, "edges": []}  # no nodes at all
    verdict = _verdict(_call(4, "eflow_validate", {"flow": doc}))
    assert verdict["ok"] is False
    assert verdict["errors"]


def test_tools_call_unknown_tool_is_32601():
    reply = _call(5, "eflow_run", {"flow": _temp_monitor()})
    assert reply["error"]["code"] == -32601


def test_tools_call_non_object_arguments_is_32602():
    reply = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "eflow_validate", "arguments": "not-an-object"},
        }
    )
    assert reply["error"]["code"] == -32602


def test_tools_call_missing_flow_argument_fails_closed():
    verdict = _verdict(_call(7, "eflow_validate", {}))
    assert verdict["ok"] is False
    assert verdict["errors"]


def test_unknown_method_is_32601():
    reply = handle_message({"jsonrpc": "2.0", "id": 8, "method": "resources/list"})
    assert reply["error"]["code"] == -32601


def test_stdio_round_trip_and_parse_error():
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        "this is not json",
    ]
    out = io.StringIO()
    McpServer(stdin=io.StringIO("\n".join(lines) + "\n"), stdout=out).serve_forever()
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    # initialize + tools/list replies, no reply for the notification,
    # and a -32700 parse error for the malformed line.
    assert len(replies) == 3
    assert replies[0]["result"]["serverInfo"]["name"] == "eflow-mcp"
    assert replies[1]["result"]["tools"][0]["name"] == "eflow_validate"
    assert replies[2]["error"]["code"] == -32700
