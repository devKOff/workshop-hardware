"""Historical Data page: sortable table of saved measurements."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .base import PageBase
from ..theme import ACCENT_NAVY, TEXT_SECONDARY


class HistoricalDataPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "Historical Data",
            "Saved measurements in a sortable table, filtered by date and time, from SQLite.",
            parent,
        )
        self._build()

    def _populate_content(self):
        # Filter row
        filters = QHBoxLayout()
        filters.setSpacing(10)
        from PySide6.QtWidgets import QLineEdit, QPushButton
        self.filter_from = QLineEdit()
        self.filter_from.setPlaceholderText("From (YYYY-MM-DD)")
        self.filter_to = QLineEdit()
        self.filter_to.setPlaceholderText("To (YYYY-MM-DD)")
        self.btn_filter = QPushButton("Apply filter")
        self.btn_filter.setObjectName("ghost")
        self.btn_clear_filter = QPushButton("Clear")
        self.btn_clear_filter.setObjectName("ghost")
        filters.addWidget(QLabel("Date:"))
        filters.addWidget(self.filter_from)
        filters.addWidget(QLabel("to"))
        filters.addWidget(self.filter_to)
        filters.addWidget(self.btn_filter)
        filters.addWidget(self.btn_clear_filter)
        filters.addStretch()
        self.add_layout(filters)

        # Table
        self.table = QTableView()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.add_widget(self.table)

        # Status
        self.status_label = QLabel("No records.")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self.add_widget(self.status_label)

        self.add_stretch()

    def set_columns(self, columns: list[str]) -> None:
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel(0, len(columns))
        model.setHorizontalHeaderLabels(columns)
        self.table.setModel(model)

    def append_row(self, values: list[str]) -> None:
        from PySide6.QtGui import QStandardItem, QStandardItemModel
        model = self.table.model()
        if model is None:
            return
        row = [QStandardItem(str(v)) for v in values]
        model.appendRow(row)
        self.status_label.setText(f"{model.rowCount()} record(s).")
