"""Live Monitoring page: real-time graphs and acquisition controls."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .base import PageBase
from ..theme import ACCENT_GREEN, ACCENT_NAVY, TEXT_SECONDARY


class LiveMonitoringPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Live Monitoring",
            "Real-time voltage, current, and power graphs with sampling controls.",
            parent,
        )
        self._build()

    def _populate_content(self):
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

        for btn in (self.btn_start, self.btn_stop, self.btn_pause,
                    self.btn_resume, self.btn_clear):
            controls.addWidget(btn)

        controls.addSpacing(20)
        controls.addWidget(QLabel("Sampling interval:"))
        from PySide6.QtWidgets import QDoubleSpinBox
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setDecimals(2)
        controls.addWidget(self.interval_spin)
        controls.addStretch()

        self.add_layout(controls)

        # Graphs placeholder
        graphs = QWidget()
        graphs.setObjectName("card")
        gv = QVBoxLayout(graphs)
        gv.setContentsMargins(14, 14, 14, 14)
        gh = QLabel("Real-time graphs")
        gh.setStyleSheet("font-weight: 700; color: #111827;")
        gv.addWidget(gh)
        self.graph_note = QLabel(
            "Voltage, current, and power graphs with bounded data buffers "
            "(background worker). Graph area rendered here."
        )
        self.graph_note.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding-top: 8px;")
        self.graph_note.setFixedHeight(150)
        gv.addWidget(self.graph_note)
        self.add_widget(graphs)

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

    def add_layout(self, layout) -> None:
        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.content_layout.addWidget(wrapper)
