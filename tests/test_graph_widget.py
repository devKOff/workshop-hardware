"""Tests for src/solar_monitor/gui/widgets/power_graph.py (bounded live graph)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from PySide6.QtWidgets import QApplication

from solar_monitor.core.measurement import Measurement
from solar_monitor.gui.widgets.power_graph import LiveGraphWidget


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_QAPP = _qapp()


def _reading(voltage_v, current_a, power_register_w=None, status="ok"):
    from datetime import datetime, timezone
    return Measurement(
        timestamp=datetime.now(timezone.utc).isoformat(),
        voltage_v=voltage_v,
        current_ma=current_a * 1000.0,
        current_a=current_a,
        power_w=power_register_w if power_register_w is not None else voltage_v * current_a,
        sensor_mode="simulated",
        sensor_status=status,
    )


def test_widget_creates_offscreen():
    graph = LiveGraphWidget(history_seconds=60.0)
    assert graph is not None
    graph.close()


def test_update_adds_points():
    graph = LiveGraphWidget(history_seconds=60.0)
    r1 = _reading(5.0, 0.1, 0.5)
    r2 = _reading(5.1, 0.2, 1.0)
    graph.update(r1)
    graph.update(r2)
    _QAPP.processEvents()
    assert len(graph._times) == 2
    assert graph._voltages[0] == 5.0
    assert graph._voltages[1] == 5.1
    graph.close()


def test_bounded_time_window():
    graph = LiveGraphWidget(history_seconds=1.0)
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Samples spaced 0.4 s apart over 2 s -> only last ~1 s should remain.
    for i in range(6):
        ts = base + __import__("datetime").timedelta(seconds=0.4 * i)
        m = Measurement(
            timestamp=ts.isoformat(), voltage_v=5.0, current_ma=100.0,
            current_a=0.1, power_w=0.5, sensor_mode="simulated", sensor_status="ok",
        )
        graph.update(m)
    _QAPP.processEvents()
    # With 1 s window and last sample at t=2.0, cutoff = 1.0 -> samples at 1.2,1.6,2.0 remain
    times = list(graph._times)
    assert len(times) <= 4, f"expected bounded buffer, got {len(times)}"
    assert all(t >= times[-1] - 1.0 for t in times)
    graph.close()


def test_clear_empties_buffers():
    graph = LiveGraphWidget(history_seconds=60.0)
    graph.update(_reading(5.0, 0.1, 0.5))
    graph.update(_reading(5.1, 0.2, 1.0))
    assert len(graph._times) == 2
    graph.clear()
    _QAPP.processEvents()
    assert len(graph._times) == 0
    assert len(graph._voltages) == 0
    graph.close()


def test_set_history_seconds():
    graph = LiveGraphWidget(history_seconds=60.0)
    graph.set_history_seconds(120.0)
    assert graph._history_seconds == 120.0
    graph.close()
