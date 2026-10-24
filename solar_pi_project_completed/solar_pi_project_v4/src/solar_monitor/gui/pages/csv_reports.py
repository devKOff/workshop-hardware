"""CSV Reports page: export historical measurements to a user-selected CSV file.

Supports optional date/time filtering so exported records match the selected
data and filters. Uses a fixed, documented column schema with consistent units
(V, A, W, Wh) and ISO-8601 timestamps. Shows export progress and success/error
messages. Handles empty datasets, invalid paths, and file permission errors.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...database.dao import list_measurements
from ...services.csv_export import CSV_COLUMNS, export_measurements
from ..theme import ACCENT_GREEN, TEXT_SECONDARY
from .base import PageBase


class CSVReportsPage(PageBase):
    def __init__(self, context, main_window, parent=None):
        self._ctx = context
        super().__init__(
            "CSV Reports",
            "Export historical measurements to a user-selected CSV file with a "
            "fixed, documented column schema.",
            parent,
        )
        self._build()

    def _build(self):
        super()._build()
        intro = QLabel(
            "Export saved measurements to CSV. The export uses a fixed column "
            "schema with consistent units (V, A, W, Wh) and ISO-8601 timestamps."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding-bottom: 10px;")
        self.add_widget(intro)

        schema = QLabel("Columns: " + ", ".join(CSV_COLUMNS))
        schema.setWordWrap(True)
        schema.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; padding-bottom: 10px;")
        self.add_widget(schema)

        # Optional date filter for the export.
        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.filter_from = QDateEdit()
        self.filter_from.setCalendarPopup(True)
        self.filter_from.setDisplayFormat("yyyy-MM-dd")
        self.filter_from.setSpecialValueText("From")
        self.filter_to = QDateEdit()
        self.filter_to.setCalendarPopup(True)
        self.filter_to.setDisplayFormat("yyyy-MM-dd")
        self.filter_to.setSpecialValueText("To")
        filters.addWidget(QLabel("Date:"))
        filters.addWidget(self.filter_from)
        filters.addWidget(QLabel("to"))
        filters.addWidget(self.filter_to)
        filters.addStretch()
        self.add_layout(filters)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.btn_export = QPushButton("Export to CSV…")
        self.btn_export.setObjectName("success")
        self.btn_export.clicked.connect(self.do_export)
        controls.addWidget(self.btn_export)
        controls.addStretch()
        self.add_layout(controls)

        self.progress_label = QLabel("Ready.")
        self.progress_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self.add_widget(self.progress_label)

        self.add_stretch()

    def _date_to_iso(self, qdate):
        if qdate is None or not qdate.isValid():
            return None
        return qdate.toPython().isoformat()

    def do_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export measurements to CSV", "exports", "CSV files (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        self.progress_label.setText("Exporting…")
        self.btn_export.setEnabled(False)
        try:
            start = self._date_to_iso(self.filter_from.date())
            end = self._date_to_iso(self.filter_to.date())
            if end:
                # Make end inclusive of the whole day.
                end = end + "T23:59:59"
            rows = list_measurements(self._ctx.conn, start=start, end=end, limit=100000)
            if not rows:
                self.progress_label.setText("No measurements to export.")
                QMessageBox.information(self, "CSV Export", "No measurements to export.")
                return
            exported = export_measurements(path, rows)
            self.progress_label.setText(f"Exported {exported} record(s) to {path}")
            QMessageBox.information(self, "CSV Export", f"Exported {exported} record(s) successfully.")
        except PermissionError as exc:
            self.progress_label.setText(f"Export failed: permission denied ({exc})")
            QMessageBox.critical(self, "CSV Export", f"Permission denied:\n{exc}")
        except OSError as exc:
            self.progress_label.setText(f"Export failed: {exc}")
            QMessageBox.critical(self, "CSV Export", f"Export failed:\n{exc}")
        except ValueError as exc:
            self.progress_label.setText(str(exc))
            QMessageBox.information(self, "CSV Export", str(exc))
        except Exception as exc:  # noqa: BLE001
            self.progress_label.setText(f"Export failed: {exc}")
            QMessageBox.critical(self, "CSV Export", f"Export failed:\n{exc}")
        finally:
            self.btn_export.setEnabled(True)
