"""Dashboard page: live readings, status, backend and sensor status."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...core.measurement_engine import EngineState
from ..theme import ACCENT_GREEN, ACCENT_NAVY, OK_TEXT, TEXT_SECONDARY, WARN_TEXT
from ..widgets.power_graph import LiveGraphWidget
from .base import PageBase


class DashboardPage(PageBase):
    def __init__(self, context, main_window, parent=None):
        self._ctx = context
        super().__init__(
            "Dashboard",
            "Live voltage, current, power, and accumulated energy with measurement status.",
            parent,
        )
        self._latest = None
        self._total_energy_wh = 0.0
        self._cards = {}  # card_key -> (card_widget, value_label, checkbox)
        self._build()

    def _build(self):
        super()._build()
        # Checkboxes to show/hide metric cards (no scrollbars needed)
        cb_row = QHBoxLayout()
        cb_row.setContentsMargins(4, 0, 4, 0)
        cb_row.setSpacing(12)

        self.cb_voltage = QCheckBox("Voltage")
        self.cb_voltage.setChecked(True)
        self.cb_voltage.setStyleSheet("color: #1f3a5f; font-weight: 600;")
        self.cb_voltage.stateChanged.connect(
            lambda _: self.voltage_card.setVisible(self.cb_voltage.isChecked())
        )
        cb_row.addWidget(self.cb_voltage)

        self.cb_current = QCheckBox("Current")
        self.cb_current.setChecked(True)
        self.cb_current.setStyleSheet("color: #1f3a5f; font-weight: 600;")
        self.cb_current.stateChanged.connect(
            lambda _: self.current_card.setVisible(self.cb_current.isChecked())
        )
        cb_row.addWidget(self.cb_current)

        self.cb_power = QCheckBox("Power")
        self.cb_power.setChecked(True)
        self.cb_power.setStyleSheet("color: #1f3a5f; font-weight: 600;")
        self.cb_power.stateChanged.connect(
            lambda _: self.power_card.setVisible(self.cb_power.isChecked())
        )
        cb_row.addWidget(self.cb_power)

        self.cb_energy = QCheckBox("Energy")
        self.cb_energy.setChecked(True)
        self.cb_energy.setStyleSheet("color: #2e7d5b; font-weight: 600;")
        self.cb_energy.stateChanged.connect(
            lambda _: self.energy_card.setVisible(self.cb_energy.isChecked())
        )
        cb_row.addWidget(self.cb_energy)

        cb_row.addStretch()
        self.add_layout(cb_row)

        # Metric cards row
        metrics = QGridLayout()
        metrics.setSpacing(14)

        self.voltage_card, self.voltage_value = self._metric_card("Voltage", "-- V", ACCENT_NAVY)
        self.current_card, self.current_value = self._metric_card("Current", "-- A", ACCENT_NAVY)
        self.power_card, self.power_value = self._metric_card("Power", "-- W", ACCENT_NAVY)
        self.energy_card, self.energy_value = self._metric_card("Energy", "-- Wh", ACCENT_GREEN)

        metrics.addWidget(self.voltage_card, 0, 0)
        metrics.addWidget(self.current_card, 0, 1)
        metrics.addWidget(self.power_card, 0, 2)
        metrics.addWidget(self.energy_card, 0, 3)
        metrics.setColumnStretch(4, 1)
        self.add_layout(metrics)

        # Status row
        status = QHBoxLayout()
        status.setSpacing(16)

        self.mode_label = QLabel("Backend: --")
        self.mode_label.setStyleSheet(f"font-weight: 700; color: {ACCENT_NAVY};")
        self.status_label = QLabel("Measurement status: --")
        self.sensor_label = QLabel("Sensor: --")
        status.addWidget(self.mode_label)
        status.addWidget(self.status_label)
        status.addWidget(self.sensor_label)
        status.addStretch()

        self.sim_note = QLabel("Simulation mode — data is simulated, not hardware readings.")
        self.sim_note.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        status.addWidget(self.sim_note)

        self.add_layout(status)

        # Live power graph (compact, bounded data buffer).
        self.graph = LiveGraphWidget(history_seconds=300.0)
        self.graph.setMaximumHeight(160)
        self.add_widget(self.graph)

        # Measurement summary
        summary_box = QWidget()
        summary_box.setObjectName("card")
        sv = QVBoxLayout(summary_box)
        sv.setContentsMargins(14, 14, 14, 14)
        sh = QLabel("Measurement summary")
        sh.setStyleSheet("font-weight: 700; color: #111827;")
        sv.addWidget(sh)
        self.summary_label = QLabel("No measurements yet.")
        self.summary_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding-top: 6px;")
        sv.addWidget(self.summary_label)
        self.add_widget(summary_box)

        self.add_stretch()
        self._refresh_status()

    def _metric_card(self, title: str, value: str, accent: str):
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        t = QLabel(title)
        t.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        v = QLabel(value)
        v.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 800;")
        layout.addWidget(t)
        layout.addWidget(v)
        card.setFixedHeight(110)
        return card, v

    def add_layout(self, layout):
        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.content_layout.addWidget(wrapper)

    def _refresh_status(self):
        engine = self._ctx.engine
        backend = engine.backend
        mode = "Simulation" if backend.mode == "simulated" else "Hardware"
        self.mode_label.setText(f"Backend: {mode}")
        self.sim_note.setVisible(backend.mode == "simulated")
        avail = backend.is_available()
        self.sensor_label.setText(
            f"Sensor: {'connected' if avail else 'unavailable'}"
        )
        self.sensor_label.setStyleSheet(
            f"font-weight: 700; color: {'#15803d' if avail else '#991b1b'};"
        )
        st = engine.state.value.capitalize()
        self.status_label.setText(f"Measurement status: {st}")

    def on_measurement(self, m, increment_wh, total_energy_wh):
        self._latest = m
        self._total_energy_wh = total_energy_wh if total_energy_wh is not None else 0.0
        self.voltage_value.setText(f"{m.voltage_v:.2f} V")
        self.current_value.setText(f"{m.current_a:.2f} A")
        self.power_value.setText(f"{m.power_w:.2f} W")
        self.energy_value.setText(f"{self._total_energy_wh:.2f} Wh")
        self.graph.update(m)
        self.status_label.setText(
            f"Measurement status: {m.sensor_status}  ({self._ctx.engine.state.value})"
        )
        self.summary_label.setText(
            f"Last sample: {m.timestamp}  ·  "
            f"{m.voltage_v:.2f} V, {m.current_a:.2f} A, {m.power_w:.2f} W  ·  "
            f"Energy: {self._total_energy_wh:.2f} Wh  ·  Mode: {m.sensor_mode}"
        )

    def on_backend_error(self, message: str):
        self.status_label.setText(f"Measurement status: error — {message}")
        self.summary_label.setText(
            f"Backend error: {message}. Check System Information for diagnostics."
        )

    def set_readings(self, voltage_v, current_a, power_w, energy_wh):
        self.voltage_value.setText(f"{voltage_v:.2f} V" if voltage_v is not None else "-- V")
        self.current_value.setText(f"{current_a:.2f} A" if current_a is not None else "-- A")
        self.power_value.setText(f"{power_w:.2f} W" if power_w is not None else "-- W")
        self.energy_value.setText(f"{energy_wh:.2f} Wh" if energy_wh is not None else "-- Wh")

    def set_status(self, mode: str, status: str, sensor: str):
        self.mode_label.setText(f"Backend: {mode}")
        self.status_label.setText(f"Measurement status: {status}")
        self.sensor_label.setText(f"Sensor: {sensor}")

    def set_summary(self, text: str):
        self.summary_label.setText(text)
