"""Energy integration with daily reset and restart-safe cumulative accounting.

How energy is computed:
  instantaneous power P (W)  ->  energy over a sample interval Δt (hours)
  ΔE (Wh) = P × (Δt / 3600)
  cumulative energy = sum of ΔE over all samples

Restart safety:
  The cumulative Wh offset is loaded from SQLite on startup
  (meta.cumulative_wh_offset) and saved after every sample. Restarting the app
  therefore continues from the last stored value instead of resetting to zero
  or double-counting.

Daily reset:
  The daily accumulator resets to 0 when the local date changes (midnight).
  The previous day's total is preserved in the daily_totals table.

Negative power:
  Only positive power contributes to generated energy. Negative readings
  (reverse current) add 0 Wh so a momentary reverse flow never subtracts
  from generated energy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from .database import Database


class EnergyTracker:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._cumulative_wh = db.cumulative_offset()
        self._daily_wh = 0.0
        self._current_day: Optional[str] = None
        self._last_ts: Optional[datetime] = None

    # ------------------------------------------------------------------ accessors

    def cumulative(self) -> float:
        return self._cumulative_wh

    def daily(self) -> float:
        return self._daily_wh

    # ------------------------------------------------------------------ integration

    def add(self, power_w: Optional[float], timestamp: str) -> Tuple[float, float, float]:
        """Integrate one sample.

        Returns (cumulative_wh, daily_wh, incremental_wh_this_sample).
        """
        now = datetime.fromisoformat(timestamp)
        day = timestamp[:10]  # YYYY-MM-DD

        incremental = 0.0

        # Daily reset at local midnight.
        if self._current_day != day:
            self._daily_wh = 0.0
            self._current_day = day

        if (
            self._last_ts is not None
            and power_w is not None
            and power_w > 0
        ):
            dt_sec = (now - self._last_ts).total_seconds()
            # Ignore absurd gaps (e.g. clock jump, app paused for hours).
            if 0 < dt_sec < self._max_gap_sec():
                incremental = power_w * (dt_sec / 3600.0)
                self._cumulative_wh += incremental
                self._daily_wh += incremental
                self.db.set_offset(self._cumulative_wh)
                self.db.upsert_daily(day, self._daily_wh)

        self._last_ts = now
        return self._cumulative_wh, self._daily_wh, incremental

    @staticmethod
    def _max_gap_sec() -> int:
        # Imported locally to avoid a circular import at module load time.
        from .config import MAX_GAP_SEC

        return MAX_GAP_SEC
