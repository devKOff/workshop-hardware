"""Settings page: sampling interval and operating mode, persisted across restarts."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.measurement_engine import MeasurementEngine
from ...database.settings import SettingsError
from ..theme import ACCENT_GREEN, ACCENT_NAVY, TEXT_SECONDARY
from .base import PageBase


class SettingsPage(PageBase):
    def __init__(self, context, main_window, parent=None):
        self._ctx = context
        super().__init__(
            "Settings",
            "Configure the sampling interval and operating mode. Settings persist across restarts.",
            parent,
        )
        self._build()

    def _build(self):
        super()._build()
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
        self.interval_spin.setValue(self._ctx.engine.sampling_interval_s)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setDecimals(2)
        form.addRow("Sampling interval:", self.interval_spin)
        hint = QLabel("Time between consecutive measurements (0.1 s to 3600 s).")
        hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        form.addRow("", hint)
        self.add_widget(interval_group)

        # Operating mode group - checkboxes instead of dropdown
        mode_group = QGroupBox("Operating mode")
        mode_group.setStyleSheet(
            "QGroupBox { font-weight: 700; color: #111827; border: 1px solid #e5e7eb; "
            "border-radius: 8px; margin-top: 10px; padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }"
        )
        mform = QFormLayout(mode_group)

        # Checkboxes for mode selection (mutually exclusive)
        self.mode_checkboxes = QHBoxLayout()
        self.mode_checkboxes.setSpacing(16)

        self.sim_checkbox = QCheckBox("Simulation")
        self.sim_checkbox.setStyleSheet("font-weight: 600; color: #1f3a5f;")
        self.sim_checkbox.stateChanged.connect(self._on_mode_checkbox_changed)
        self.mode_checkboxes.addWidget(self.sim_checkbox)

        self.hw_checkbox = QCheckBox("Hardware")
        self.hw_checkbox.setStyleSheet("font-weight: 600; color: #2e7d5b;")
        self.hw_checkbox.stateChanged.connect(self._on_mode_checkbox_changed)
        self.mode_checkboxes.addWidget(self.hw_checkbox)

        self.mode_checkboxes.addStretch()
        mform.addRow("Mode:", self.mode_checkboxes)

        # Probe hardware on page load so availability is known and the
        # Hardware option is enabled when the INA219 is detected.
        self._ctx.hw_backend.probe()
        hw_available = self._ctx.hw_backend.is_available()
        if not hw_available:
            self.hw_checkbox.setEnabled(False)
            self.hw_checkbox.setToolTip(
                "Hardware mode unavailable: INA219 not initialised on this machine."
            )
        else:
            self.hw_checkbox.setToolTip("Hardware: Raspberry Pi with INA219 over I²C.")
        self.sim_checkbox.setToolTip("Simulation: available everywhere (Windows development).")

        # Set initial state from saved settings
        current = self._ctx.settings.get("sensor_mode")
        self.sim_checkbox.setChecked(current == "simulated")
        self.hw_checkbox.setChecked(current == "hardware")

        mode_hint = QLabel(
            "Simulation: available everywhere (Windows development). Hardware: "
            "Raspberry Pi with INA219 over I²C. Mode is stored explicitly and is "
            "never silently switched from hardware to simulation."
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

    def _on_mode_checkbox_changed(self, state):
        """Keep simulation and hardware checkboxes mutually exclusive."""
        sender = self.sender()
        if state:  # checkbox was checked
            if sender is self.sim_checkbox:
                self.hw_checkbox.setChecked(False)
            elif sender is self.hw_checkbox:
                self.sim_checkbox.setChecked(False)

    def _save(self):
        try:
            interval = self.interval_spin.value()
            self._ctx.settings.set("sampling_interval_s", interval)
            self._ctx.engine.set_sampling_interval(interval)

            # Determine mode from checkboxes
            if self.hw_checkbox.isChecked():
                new_mode = "hardware"
            else:
                new_mode = "simulated"

            # Probe hardware only when the user explicitly selects it; never
            # silently switch hardware -> simulation.
            if new_mode == "hardware":
                self._ctx.hw_backend.probe()

            # Never silently switch hardware -> simulation. If the user selects
            # hardware but hardware is unavailable, reject with an explanation.
            if new_mode == "hardware" and not self._ctx.hw_backend.is_available():
                raise SettingsError(
                    "Hardware mode unavailable: INA219 sensor not initialised. "
                    "Check wiring, I²C enablement, and System Information diagnostics."
                )

            self._ctx.settings.set("sensor_mode", new_mode)

            # Switch backend only when the mode actually changes and is valid.
            if new_mode != self._ctx.backend.mode:
                self._ctx.engine.shutdown()
                self._ctx.backend = (
                    self._ctx.hw_backend if new_mode == "hardware" else self._ctx.sim_backend
                )
                self._ctx.engine = MeasurementEngine(self._ctx.backend, db_path=self._ctx.db_path)
                self._mw.ctx = self._ctx
                self._mw.ctx.engine.measurement_taken.connect(self._mw._on_measurement_taken)
                self._mw.ctx.engine.backend_error.connect(self._mw._on_backend_error)

            self.status_label.setText(
                f"Saved: interval={interval}s, mode={new_mode}."
            )
            self.status_label.setStyleSheet(f"color: #15803d; font-size: 12px;")
        except SettingsError as exc:
            self.status_label.setText(f"Invalid setting: {exc}")
            self.status_label.setStyleSheet(f"color: #991b1b; font-size: 12px;")
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Save failed: {exc}")
            self.status_label.setStyleSheet(f"color: #991b1b; font-size: 12px;")