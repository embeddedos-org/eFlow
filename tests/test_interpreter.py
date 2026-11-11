# SPDX-License-Identifier: MIT
"""Tests for the eFlow host interpreter prototype (v1)."""
import json
import math
import os

import pytest

from eflow.interpreter import FlowError, load, run_flow, tick

FLOWS = os.path.join(os.path.dirname(__file__), "..", "eflow", "flows")


def _flow(name):
    with open(os.path.join(FLOWS, name), encoding="utf-8") as f:
        return json.load(f)


def _mini(nodes, edges):
    return {"flow": "t", "version": 1, "nodes": nodes, "edges": edges}


class TestLoad:
    def test_sample_flows_load(self):
        for name in ("temp_monitor.json", "fan_control.json"):
            nodes, edges, order = load(_flow(name))
            assert len(order) == len(nodes)

    def test_topo_order_respects_edges(self):
        flow = _mini(
            [{"id": "a", "type": "sensor.tmp117", "params": {}},
             {"id": "b", "type": "filter.moving_avg", "params": {}},
             {"id": "c", "type": "debug.console", "params": {}}],
            [{"from": "a:out", "to": "b:in"},
             {"from": "b:out", "to": "c:in"}],
        )
        _, _, order = load(flow)
        assert order == ["a", "b", "c"]

    def test_cycle_rejected_with_path(self):
        flow = _mini(
            [{"id": "a", "type": "filter.moving_avg", "params": {}},
             {"id": "b", "type": "filter.moving_avg", "params": {}}],
            [{"from": "a:out", "to": "b:in"},
             {"from": "b:out", "to": "a:in"}],
        )
        with pytest.raises(FlowError, match="cycle"):
            load(flow)

    def test_unknown_node_type(self):
        flow = _mini([{"id": "a", "type": "nope.x", "params": {}}], [])
        with pytest.raises(FlowError, match="unknown type"):
            load(flow)

    def test_duplicate_id(self):
        flow = _mini(
            [{"id": "a", "type": "sensor.tmp117", "params": {}},
             {"id": "a", "type": "sensor.tmp117", "params": {}}], [])
        with pytest.raises(FlowError, match="duplicate"):
            load(flow)

    def test_bad_port_direction(self):
        # sensor.tmp117 has no *input* port "out"
        flow = _mini(
            [{"id": "a", "type": "sensor.tmp117", "params": {}},
             {"id": "b", "type": "debug.console", "params": {}}],
            [{"from": "a:out", "to": "a:out"}],
        )
        with pytest.raises(FlowError, match="no in port"):
            load(flow)

    def test_unknown_node_in_edge(self):
        flow = _mini([{"id": "a", "type": "sensor.tmp117", "params": {}}],
                     [{"from": "zzz:out", "to": "a:out"}])
        with pytest.raises(FlowError, match="unknown node"):
            load(flow)

    def test_type_mismatch_rejected(self):
        # logic.threshold emits bool; gpio_led wants bool — ok; but feeding
        # the bool into moving_avg (float) must fail.
        flow = _mini(
            [{"id": "t", "type": "logic.threshold",
              "params": {"level": 1}},
             {"id": "f", "type": "filter.moving_avg", "params": {}}],
            [{"from": "t:out", "to": "f:in"}],
        )
        with pytest.raises(FlowError, match="type mismatch"):
            load(flow)

    def test_unconnected_input_rejected(self):
        flow = _mini(
            [{"id": "c", "type": "debug.console", "params": {}}], [])
        with pytest.raises(FlowError, match="no incoming edge"):
            load(flow)

    def test_input_driven_twice_rejected(self):
        # Two edges into one input port: tick() would keep only the last
        # edge's value, so load() must reject the flow.
        flow = _mini(
            [{"id": "s", "type": "sensor.tmp117", "params": {}},
             {"id": "t", "type": "logic.threshold", "params": {}},
             {"id": "c", "type": "debug.console", "params": {}}],
            [{"from": "s:out", "to": "t:in"},
             {"from": "s:out", "to": "c:in"},
             {"from": "t:out", "to": "c:in"}],
        )
        with pytest.raises(FlowError, match="more than one edge"):
            load(flow)

    def test_bad_version_rejected(self):
        with pytest.raises(FlowError, match="version"):
            load({"flow": "t", "version": 99, "nodes": [], "edges": []})

    def test_any_port_warns(self):
        flow = _mini(
            [{"id": "a", "type": "sensor.tmp117", "params": {}},
             {"id": "c", "type": "debug.console", "params": {}}],
            [{"from": "a:out", "to": "c:in"}],
        )
        with pytest.warns(UserWarning, match="'any' port"):
            load(flow)


class TestNodes:
    def test_sensor_deterministic(self):
        log1 = run_flow(_flow("temp_monitor.json"), ticks=10)
        log2 = run_flow(_flow("temp_monitor.json"), ticks=10)
        assert log1 == log2

    def test_sensor_waveform(self):
        flow = _flow("temp_monitor.json")
        log = run_flow(flow, ticks=5)
        vals = log["console"]
        raw = [25.0 + 5.0 * math.sin(t * 0.5) for t in range(5)]
        # console sees the moving average (window=8, partial at the start)
        assert vals[0] == pytest.approx(raw[0])
        assert vals[1] == pytest.approx(sum(raw[:2]) / 2)
        assert vals[4] == pytest.approx(sum(raw[:5]) / 5)

    def test_moving_avg_smooths(self):
        # window=1 passes through; window=8 lags the wave
        f1 = _flow("temp_monitor.json")
        log = run_flow(f1, ticks=16)
        raw = [25.0 + 5.0 * math.sin(t * 0.5) for t in range(16)]
        assert log["console"][-1] == pytest.approx(sum(raw[-8:]) / 8)

    def test_threshold_hysteresis(self):
        flow = _flow("fan_control.json")
        log = run_flow(flow, ticks=40)
        states = [on for _pin, on in log["gpio_led"]]
        # wave peaks at 30 > 27.5 -> on; troughs at 20 < 26.5 -> off
        assert True in states and False in states
        # hysteresis: once on, stays on until below 26.5
        first_on = states.index(True)
        assert all(states[first_on:first_on + 3])

    def test_console_is_host_sink(self):
        log = run_flow(_flow("temp_monitor.json"), ticks=3)
        assert len(log["console"]) == 3


class TestParams:
    @staticmethod
    def _avg(window):
        return _mini(
            [{"id": "s", "type": "sensor.tmp117", "params": {}},
             {"id": "f", "type": "filter.moving_avg",
              "params": {"window": window}},
             {"id": "c", "type": "debug.console", "params": {}}],
            [{"from": "s:out", "to": "f:in"},
             {"from": "f:out", "to": "c:in"}],
        )

    @staticmethod
    def _threshold(params):
        return _mini(
            [{"id": "s", "type": "sensor.tmp117", "params": {}},
             {"id": "t", "type": "logic.threshold", "params": params},
             {"id": "c", "type": "debug.console", "params": {}}],
            [{"from": "s:out", "to": "t:in"},
             {"from": "t:out", "to": "c:in"}],
        )

    @pytest.mark.parametrize(
        "window", [0, -1, 2.5, "8", True, None, 2**31,
                   pytest.param(2**63, id="2**63"),
                   pytest.param(10**400, id="10**400")])
    def test_bad_window_rejected_at_load(self, window):
        with pytest.raises(FlowError, match="'window' must be an integer"):
            load(self._avg(window))

    def test_window_at_max_loads(self):
        nodes, _edges, _order = load(self._avg(2**31 - 1))
        assert nodes["f"]._window.maxlen == 2**31 - 1

    def test_window_one_runs(self):
        log = run_flow(self._avg(1), ticks=3)
        assert log["console"] == [
            pytest.approx(25.0 + 5.0 * math.sin(t * 0.5)) for t in range(3)]

    @pytest.mark.parametrize("params", [
        {"level": "hot"}, {"level": True}, {"level": None},
        {"level": float("nan")}, {"level": 10 ** 400}, {"hysteresis": "1"},
    ])
    def test_bad_threshold_params_rejected_at_load(self, params):
        with pytest.raises(FlowError, match="must be a finite number"):
            load(self._threshold(params))

    def test_integer_threshold_params_accepted(self):
        log = run_flow(self._threshold({"level": 25, "hysteresis": 2}),
                       ticks=3)
        assert len(log["console"]) == 3


class TestTick:
    def test_tick_returns_port_values(self):
        nodes, edges, order = load(_flow("temp_monitor.json"))
        vals = tick(nodes, edges, order, 0, {})
        assert vals[("temp", "out")] == pytest.approx(25.0)
