"""Live Monitoring page: real-time graphs and acquisition controls."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.measurement_engine import EngineState
from ..theme import ACCENT_GREEN, ACCENT_NAVY, TEXT_SECONDARY
from ..widgets.power_graph import LiveGraphWidget
from .base import PageBase


class LiveMonitoringPage(PageBase):
    def __init__(self, context, main_window, parent=None):
        self._ctx = context
        self._mw = main_window
        super().__init__(
            "Live Monitoring",
            "Real-time voltage, current, and power graphs with sampling controls.",
            parent,
        )
        self._build()

    def _build(self):
        super()._build()
        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("success")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("danger")
        self.btn_pause = QPushButton("Pause")
        self.btn_resume = QPushButton("Resume")
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("ghost")

        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_resume.clicked.connect(self._resume)
        self.btn_clear.clicked.connect(self._clear)

        for btn in (self.btn_start, self.btn_stop, self.btn_pause,
                    self.btn_resume, self.btn_clear):
            controls.addWidget(btn)

        controls.addSpacing(20)
        controls.addWidget(QLabel("Sampling interval:"))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600.0)
        self.interval_spin.setValue(self._ctx.engine.sampling_interval_s)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setDecimals(2)
        self.interval_spin.valueChanged.connect(self._interval_changed)
        controls.addWidget(self.interval_spin)
        controls.addStretch()

        self.add_layout(controls)

        # Real-time graphs (bounded data buffers, background worker).
        self.graph = LiveGraphWidget(history_seconds=300.0)
        self.graph.setMinimumHeight(260)
        self.add_widget(self.graph)

        # Latest measurement + sampling status
        status = QHBoxLayout()
        status.setSpacing(16)
        self.latest_label = QLabel("Latest measurement: --")
        self.status_label = QLabel("Sampling status: idle")
        self.status_label.setStyleSheet(f"font-weight: 700; color: {ACCENT_NAVY};")
        status.addWidget(self.latest_label)
        status.addWidget(self.status_label)
        status.addStretch()
        self.add_layout(status)

        self.add_stretch()
        self._refresh_ui()

    def add_layout(self, layout):
        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.content_layout.addWidget(wrapper)

    def _refresh_ui(self):
        engine = self._ctx.engine
        st = engine.state
        running = st == EngineState.RUNNING
        paused = st == EngineState.PAUSED
        self.btn_start.setEnabled(st in (EngineState.IDLE, EngineState.STOPPED))
        self.btn_stop.setEnabled(running or paused)
        self.btn_pause.setEnabled(running)
        self.btn_resume.setEnabled(paused)
        self.btn_clear.setEnabled(st != EngineState.RUNNING)
        self.interval_spin.setEnabled(st != EngineState.RUNNING)
        self.status_label.setText(f"Sampling status: {st.value}")
        self.status_label.setStyleSheet(
            f"font-weight: 700; color: "
            f"{'#15803d' if running else ('#b45309' if paused else '#1f3a5f')};"
        )

    def _start(self):
        self._ctx.engine.start()
        self._refresh_ui()

    def _stop(self):
        self._ctx.engine.stop()
        self._refresh_ui()

    def _pause(self):
        self._ctx.engine.pause()
        self._refresh_ui()

    def _resume(self):
        self._ctx.engine.resume()
        self._refresh_ui()

    def _clear(self):
        self.latest_label.setText("Latest measurement: --")
        self.graph.clear()

    def toggle_monitoring(self):
        engine = self._ctx.engine
        if engine.state in (EngineState.IDLE, EngineState.STOPPED):
            self._start()
        elif engine.state == EngineState.RUNNING:
            self._stop()
        else:
            self._start()

    def _interval_changed(self, value):
        self._ctx.engine.set_sampling_interval(value)

    def on_measurement(self, m, increment_wh, total_energy_wh):
        self.graph.update(m)
        self.latest_label.setText(
            f"Latest measurement: {m.timestamp}  {m.voltage_v:.2f} V, "
            f"{m.current_a:.2f} A, {m.power_w:.2f} W"
        )

    def on_backend_error(self, message: str):
        self.status_label.setText(f"Sampling status: error — {message}")
