"""CSV Reports page: export historical measurements to a user-selected CSV file."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .base import PageBase
from ..theme import ACCENT_GREEN, TEXT_SECONDARY


class CSVReportsPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "CSV Reports",
            "Export historical measurements to a user-selected CSV file with a "
            "fixed, documented column schema.",
            parent,
        )
        self._build()

    def _populate_content(self):
        intro = QLabel(
            "Export saved measurements to CSV. The export uses a fixed column "
            "schema with consistent units (V, A, W, Wh) and ISO-8601 timestamps."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding-bottom: 10px;")
        self.add_widget(intro)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.btn_export = QPushButton("Export to CSV…")
        self.btn_export.setObjectName("success")
        self.btn_export.clicked.connect(self._export)
        controls.addWidget(self.btn_export)
        controls.addStretch()
        self.add_layout(controls)

        self.progress_label = QLabel("Ready.")
        self.progress_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self.add_widget(self.progress_label)

        self.add_stretch()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export measurements to CSV", "exports", "CSV files (*.csv)"
        )
        if not path:
            return
        self.progress_label.setText("Exporting…")
        try:
            from services.csv_export import export_measurements
        except Exception as exc:  # pragma: no cover - service wired in phase 8
            self.progress_label.setText("Export service not available yet.")
            QMessageBox.information(
                self, "CSV Export",
                f"CSV export service will be available in Phase 8.\n\n({exc})",
            )
            return
        try:
            exported = export_measurements(path)
            self.progress_label.setText(f"Exported {exported} record(s) to {path}")
            QMessageBox.information(self, "CSV Export", f"Exported {exported} record(s) successfully.")
        except Exception as exc:  # noqa: BLE001
            self.progress_label.setText(f"Export failed: {exc}")
            QMessageBox.critical(self, "CSV Export", f"Export failed:\n{exc}")
