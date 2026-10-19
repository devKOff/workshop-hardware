"""Live graph widget: bounded-data-buffer voltage/current/power plot with
checkboxes to show/hide individual lines (no scrollbars needed)."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ...core.measurement import Measurement


class LiveGraphWidget(QWidget):
    """Compact live plot of voltage, current, and power.

    Uses bounded data buffers (deque) sized by a time window so memory stays
    constant regardless of how long the acquisition runs. All updates happen
    on the GUI thread via the engine's poll timer.

    Checkboxes let the user show/hide each curve instead of scrolling.
    """

    def __init__(self, history_seconds: float = 300.0, parent: QWidget | None = None):
        super().__init__(parent)
        self._history_seconds = float(history_seconds)
        self._t0 = None
        self._times: deque[float] = deque()
        self._voltages: deque[float] = deque()
        self._currents: deque[float] = deque()
        self._powers: deque[float] = deque()
        self._max_points = 5000  # hard cap so buffers never grow unbounded
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Checkbox row: show/hide individual curves (no scrollbars needed)
        cb_row = QHBoxLayout()
        cb_row.setContentsMargins(4, 0, 4, 0)
        cb_row.setSpacing(12)

        self.cb_voltage = QCheckBox("Voltage (V)")
        self.cb_voltage.setChecked(True)
        self.cb_voltage.setStyleSheet("color: #1f3a5f; font-weight: 600;")
        self.cb_voltage.stateChanged.connect(
            lambda _: self.curve_v.setVisible(self.cb_voltage.isChecked())
        )
        cb_row.addWidget(self.cb_voltage)

        self.cb_current = QCheckBox("Current (A)")
        self.cb_current.setChecked(True)
        self.cb_current.setStyleSheet("color: #2e7d5b; font-weight: 600;")
        self.cb_current.stateChanged.connect(
            lambda _: self.curve_i.setVisible(self.cb_current.isChecked())
        )
        cb_row.addWidget(self.cb_current)

        self.cb_power = QCheckBox("Power (W)")
        self.cb_power.setChecked(True)
        self.cb_power.setStyleSheet("color: #b45309; font-weight: 600;")
        self.cb_power.stateChanged.connect(
            lambda _: self.curve_p.setVisible(self.cb_power.isChecked())
        )
        cb_row.addWidget(self.cb_power)

        cb_row.addStretch()
        layout.addLayout(cb_row)

        # Plot area
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("left", "Value")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setTitle("Live Power", color="#111827")
        self.curve_v = self.plot.plot(
            pen=pg.mkPen("#1f3a5f", width=2), name="Voltage (V)"
        )
        self.curve_i = self.plot.plot(
            pen=pg.mkPen("#2e7d5b", width=2), name="Current (A)"
        )
        self.curve_p = self.plot.plot(
            pen=pg.mkPen("#b45309", width=2), name="Power (W)"
        )
        self.plot.addLegend()
        layout.addWidget(self.plot)

    def update(self, m: Measurement) -> None:
        """Append one measurement and redraw the bounded curves."""
        ts = datetime.fromisoformat(m.timestamp)
        if self._t0 is None:
            self._t0 = ts
        t = (ts - self._t0).total_seconds()

        self._times.append(t)
        self._voltages.append(m.voltage_v)
        self._currents.append(m.current_a)
        self._powers.append(m.power_w)

        # Enforce the time-window bound (bounded data buffer).
        cutoff = t - self._history_seconds
        while self._times and self._times[0] < cutoff:
            self._times.popleft()
            self._voltages.popleft()
            self._currents.popleft()
            self._powers.popleft()

        # Hard cap on point count so memory stays constant.
        while len(self._times) > self._max_points:
            self._times.popleft()
            self._voltages.popleft()
            self._currents.popleft()
            self._powers.popleft()

        self.curve_v.setData(list(self._times), list(self._voltages))
        self.curve_i.setData(list(self._times), list(self._currents))
        self.curve_p.setData(list(self._times), list(self._powers))

        if self._times:
            self.plot.setXRange(max(0.0, t - self._history_seconds), t, padding=0.02)

    def clear(self) -> None:
        """Clear all buffers and curves."""
        self._t0 = None
        self._times.clear()
        self._voltages.clear()
        self._currents.clear()
        self._powers.clear()
        self.curve_v.clear()
        self.curve_i.clear()
        self.curve_p.clear()

    def set_history_seconds(self, seconds: float) -> None:
        self._history_seconds = float(seconds)
