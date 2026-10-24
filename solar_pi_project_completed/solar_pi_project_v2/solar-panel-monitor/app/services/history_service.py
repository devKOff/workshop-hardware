"""Read-only history queries over the measurements database."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from app.database import Database
from app.models import DailyEnergy, EnergySummary, Measurement
from app.services.energy_service import (
    compute_daily_energy,
    compute_summary,
    integrate_energy,
)


class HistoryService:
    """Service for querying historical measurements and energy summaries."""

    def __init__(self, database: Database) -> None:
        self.db = database

    def get_latest(self) -> Optional[Measurement]:
        return self.db.get_latest()

    def get_recent(self, limit: int = 100) -> List[Measurement]:
        return self.db.get_measurements(limit=limit)

    def get_range(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Measurement]:
        return self.db.get_measurements(start=start, end=end, limit=limit)

    def get_energy_summary(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> EnergySummary:
        measurements = self.db.get_measurements(start=start, end=end)
        return compute_summary(measurements)

    def get_total_energy_wh(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> float:
        measurements = self.db.get_measurements(start=start, end=end)
        return integrate_energy(measurements)

    def get_daily_energy(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[DailyEnergy]:
        # Compute daily energy from persisted measurements so midnight rollover
        # is always handled correctly and data survives restarts without relying
        # on a separately maintained summary table.
        measurements = self.db.get_measurements()
        daily = compute_daily_energy(measurements)
        if start_date is not None:
            daily = [d for d in daily if d.date >= start_date]
        if end_date is not None:
            daily = [d for d in daily if d.date <= end_date]
        return daily

    def compute_daily_from_measurements(
        self, measurements: Optional[List[Measurement]] = None
    ) -> List[DailyEnergy]:
        if measurements is None:
            measurements = self.db.get_measurements()
        return compute_daily_energy(measurements)

    def measurement_count(self) -> int:
        return self.db.get_measurement_count()
