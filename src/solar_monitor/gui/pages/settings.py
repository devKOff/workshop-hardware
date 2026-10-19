"""Settings page: sampling interval and operating mode."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .base import PageBase
from ..theme import ACCENT_NAVY, TEXT_SECONDARY


class SettingsPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Settings",
            "Configure the sampling interval and operating mode. Settings persist across restarts.",
            parent,
        )
        self._build()

    def _populate_content(self):
        # Sampling interval group
        interval_group = QGroupBox("Sampling")
        interval_group.setStyleSheet(
            "QGroupBox { font-weight: 700; color: #111827; border: 1px solid #e5e7eb; "
            "border-radius: 8px; margin-top: 10px; padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }"
        )
        form = QFormLayout(interval_group)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setDecimals(2)
        form.addRow("Sampling interval:", self.interval_spin)
        hint = QLabel("Time between consecutive measurements.")
        hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        form.addRow("", hint)
        self.add_widget(interval_group)

        # Operating mode group
        mode_group = QGroupBox("Operating mode")
        mode_group.setStyleSheet(
            "QGroupBox { font-weight: 700; color: #111827; border: 1px solid #e5e7eb; "
            "border-radius: 8px; margin-top: 10px; padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }"
        )
        mform = QFormLayout(mode_group)
        from PySide6.QtWidgets import QComboBox
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Simulation", "Hardware"])
        self.mode_combo.setCurrentIndex(0)
        mform.addRow("Mode:", self.mode_combo)
        mode_hint = QLabel(
            "Simulation: available everywhere. Hardware: Raspberry Pi with INA219 "
            "over I²C. Mode is stored explicitly and never silently switched."
        )
        mode_hint.setWordWrap(True)
        mode_hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        mform.addRow("", mode_hint)
        self.add_widget(mode_group)

        self.btn_save = QPushButton("Save settings")
        self.btn_save.setObjectName("success")
        self.btn_save.clicked.connect(self._save)
        self.add_widget(self.btn_save)

        self.status_label = QLabel("Settings not yet saved.")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self.add_widget(self.status_label)

        self.add_stretch()

    def _save(self):
        self.status_label.setText(
            f"Settings saved: interval={self.interval_spin.value()}s, "
            f"mode={self.mode_combo.currentText()}."
        )
