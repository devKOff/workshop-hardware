"""Dashboard page: live readings, status, backend and sensor status."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .base import PageBase
from ..theme import ACCENT_GREEN, ACCENT_NAVY, TEXT_SECONDARY


class DashboardPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Dashboard",
            "Live voltage, current, power, and accumulated energy with measurement status.",
            parent,
        )
        self._build()

    def _populate_content(self):
        # Metric cards row
        metrics = QGridLayout()
        metrics.setSpacing(14)

        self.voltage_label, self.voltage_value = self._metric_card("Voltage", "-- V", ACCENT_NAVY)
        self.current_label, self.current_value = self._metric_card("Current", "-- A", ACCENT_NAVY)
        self.power_label, self.power_value = self._metric_card("Power", "-- W", ACCENT_NAVY)
        self.energy_label, self.energy_value = self._metric_card("Energy", "-- Wh", ACCENT_GREEN)

        metrics.addWidget(self.voltage_label, 0, 0)
        metrics.addWidget(self.current_label, 0, 1)
        metrics.addWidget(self.power_label, 0, 2)
        metrics.addWidget(self.energy_label, 0, 3)
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

        sim_note = QLabel("Simulation mode — data is simulated, not hardware readings.")
        sim_note.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        status.addWidget(sim_note)

        self.add_layout(status)

        # Live power graph placeholder
        graph_box = QWidget()
        graph_box.setObjectName("card")
        gv = QVBoxLayout(graph_box)
        gv.setContentsMargins(14, 14, 14, 14)
        from PySide6.QtWidgets import QLabel as _QLabel
        gh = _QLabel("Live power graph")
        gh.setStyleSheet("font-weight: 700; color: #111827;")
        gv.addWidget(gh)
        self.graph_placeholder = _QLabel("Graph area (compact live power graph).")
        self.graph_placeholder.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; padding-top: 8px;"
        )
        self.graph_placeholder.setFixedHeight(120)
        gv.addWidget(self.graph_placeholder)
        self.add_widget(graph_box)

        # Measurement summary
        summary_box = QWidget()
        summary_box.setObjectName("card")
        sv = QVBoxLayout(summary_box)
        sv.setContentsMargins(14, 14, 14, 14)
        sh = _QLabel("Measurement summary")
        sh.setStyleSheet("font-weight: 700; color: #111827;")
        sv.addWidget(sh)
        self.summary_label = _QLabel("No measurements yet.")
        self.summary_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding-top: 6px;")
        sv.addWidget(self.summary_label)
        self.add_widget(summary_box)

        self.add_stretch()

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

    def add_layout(self, layout) -> None:
        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.content_layout.addWidget(wrapper)

    # --- Public update API (wired in later phases) -------------------------
    def set_readings(self, voltage_v: float | None, current_a: float | None,
                     power_w: float | None, energy_wh: float | None) -> None:
        def fmt(v, unit):
            return f"{v:.2f} {unit}" if v is not None else f"-- {unit}"
        self.voltage_value.setText(fmt(voltage_v, "V"))
        self.current_value.setText(fmt(current_a, "A"))
        self.power_value.setText(fmt(power_w, "W"))
        self.energy_value.setText(fmt(energy_wh, "Wh"))

    def set_status(self, mode: str, status: str, sensor: str) -> None:
        self.mode_label.setText(f"Backend: {mode}")
        self.status_label.setText(f"Measurement status: {status}")
        self.sensor_label.setText(f"Sensor: {sensor}")

    def set_summary(self, text: str) -> None:
        self.summary_label.setText(text)
