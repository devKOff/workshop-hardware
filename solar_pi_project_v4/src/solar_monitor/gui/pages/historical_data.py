"""Historical Data page: sortable table of saved measurements from SQLite."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...database.dao import list_measurements
from ..theme import ACCENT_NAVY, TEXT_SECONDARY
from .base import PageBase

COLUMNS = [
    "Timestamp (UTC)",
    "Session",
    "Mode",
    "Status",
    "Voltage (V)",
    "Current (A)",
    "Power (W)",
    "Energy Incr. (Wh)",
    "Daily Energy (Wh)",
    "Total Energy (Wh)",
]


class HistoricalDataPage(PageBase):
    def __init__(self, context, main_window, parent=None):
        self._ctx = context
        super().__init__(
            "Historical Data",
            "Saved measurements in a sortable table, filtered by date and time, from SQLite.",
            parent,
        )
        self._rows = []
        self._build()

    def _build(self):
        super()._build()
        # Filter row
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
        self._filter_active = False
        self.btn_filter = QPushButton("Apply filter")
        self.btn_filter.setObjectName("ghost")
        self.btn_clear_filter = QPushButton("Clear")
        self.btn_clear_filter.setObjectName("ghost")
        self.btn_filter.clicked.connect(self._apply_filter)
        self.btn_clear_filter.clicked.connect(self._clear_filter)
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
        self.table.setSortingEnabled(True)
        self.add_widget(self.table)

        # Status
        self.status_label = QLabel("No records.")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self.add_widget(self.status_label)

        self.add_stretch()
        self._load()

    def add_layout(self, layout):
        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.content_layout.addWidget(wrapper)

    def _date_to_iso(self, qdate):
        if qdate is None or not qdate.isValid():
            return None
        return qdate.toPython().isoformat()

    def _load(self, start=None, end=None):
        # Make end inclusive of the whole day.
        if end:
            end = end + "T23:59:59"
        self._rows = list_measurements(
            self._ctx.conn, start=start, end=end, limit=5000
        )
        self._populate()

    def _apply_filter(self):
        self._filter_active = True
        start = self._date_to_iso(self.filter_from.date())
        end = self._date_to_iso(self.filter_to.date())
        self._load(start=start, end=end)

    def _clear_filter(self):
        self._filter_active = False
        self.filter_from.setDate(self.filter_from.date().addYears(-50))
        self.filter_to.setDate(self.filter_to.date().addYears(50))
        self._load()

    def _populate(self):
        model = QStandardItemModel(0, len(COLUMNS))
        model.setHorizontalHeaderLabels(COLUMNS)
        for row in self._rows:
            items = [
                QStandardItem(str(row["timestamp"])),
                QStandardItem(str(row["session_id"])),
                QStandardItem(str(row["sensor_mode"])),
                QStandardItem(str(row["sensor_status"])),
                QStandardItem(f"{row['voltage_v']:.3f}"),
                QStandardItem(f"{row['current_a']:.3f}"),
                QStandardItem(f"{row['power_w']:.3f}"),
                QStandardItem("" if row["energy_wh_increment"] is None else f"{row['energy_wh_increment']:.6f}"),
                QStandardItem("" if row["daily_energy_wh"] is None else f"{row['daily_energy_wh']:.6f}"),
                QStandardItem("" if row["total_energy_wh"] is None else f"{row['total_energy_wh']:.6f}"),
            ]
            row_idx = model.rowCount()
            for col, item in enumerate(items):
                item.setEditable(False)
                if col in (4, 5, 6, 7, 8, 9):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                model.setItem(row_idx, col, item)
        self.table.setModel(model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.status_label.setText(f"{self.table.model().rowCount()} record(s) shown.")
