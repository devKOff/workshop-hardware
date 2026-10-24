"""Energy calculations: timestamp-based integration of power over time.

Energy (Wh) is computed by integrating instantaneous power (W) over elapsed
time using the trapezoidal rule between consecutive samples:

    energy_wh += ((power1 + power2) / 2) * (t2 - t1) / 3600

This correctly handles irregular sampling intervals, missing samples (larger
time gaps are naturally accounted for), and application restarts (energy is
recomputed from persisted measurements, so historical data survives restarts).

Limits of recovery when the application is stopped: while the monitor is not
running, no samples are taken, so energy generated during downtime is not
recorded and is treated as unknown (not assumed to be zero). Accumulated
energy only reflects periods when the sampler was active.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Sequence

from app.models import DailyEnergy, EnergySummary, Measurement


def _to_utc_naive(ts: datetime) -> datetime:
    """Normalize a datetime to a naive local timestamp for arithmetic."""
    if ts.tzinfo is not None:
        ts = ts.astimezone(None).replace(tzinfo=None)
    return ts


def integrate_energy(measurements: Sequence[Measurement]) -> float:
    """Return total watt-hours using trapezoidal integration over timestamps.

    Returns 0.0 when fewer than two samples are supplied (no interval to
    integrate over). Measurements need not be pre-sorted; they are sorted
    internally by timestamp.
    """
    if len(measurements) < 2:
        return 0.0

    ordered = sorted(measurements, key=lambda m: _to_utc_naive(m.timestamp))
    total_wh = 0.0

    for prev, curr in zip(ordered, ordered[1:]):
        t_prev = _to_utc_naive(prev.timestamp)
        t_curr = _to_utc_naive(curr.timestamp)
        delta_hours = (t_curr - t_prev).total_seconds() / 3600.0
        if delta_hours <= 0:
            # Duplicate or out-of-order timestamps: skip the degenerate interval.
            continue
        avg_power_w = (prev.power_w + curr.power_w) / 2.0
        total_wh += avg_power_w * delta_hours

    return total_wh


def compute_summary(measurements: Sequence[Measurement]) -> EnergySummary:
    """Compute aggregate statistics over a list of measurements.

    An empty sequence yields a zeroed summary with sample_count 0.
    """
    ordered = sorted(measurements, key=lambda m: _to_utc_naive(m.timestamp))
    count = len(ordered)

    if count == 0:
        now = datetime.now()
        return EnergySummary(
            period_start=now,
            period_end=now,
            total_energy_wh=0.0,
            avg_power_w=0.0,
            min_power_w=0.0,
            max_power_w=0.0,
            sample_count=0,
            duration_hours=0.0,
        )

    powers = [m.power_w for m in ordered]
    total_wh = integrate_energy(ordered)
    start_ts = _to_utc_naive(ordered[0].timestamp)
    end_ts = _to_utc_naive(ordered[-1].timestamp)
    duration_hours = max((end_ts - start_ts).total_seconds() / 3600.0, 0.0)

    return EnergySummary(
        period_start=ordered[0].timestamp,
        period_end=ordered[-1].timestamp,
        total_energy_wh=total_wh,
        avg_power_w=sum(powers) / count,
        min_power_w=min(powers),
        max_power_w=max(powers),
        sample_count=count,
        duration_hours=duration_hours,
    )


def compute_daily_energy(
    measurements: Sequence[Measurement],
) -> List[DailyEnergy]:
    """Group measurements by local date and return per-day energy summaries.

    Days are determined from the timestamp's calendar date (local time).
    Each day's energy is integrated independently so that midnight rollover
    is handled correctly: energy never carries over from one day to the next.
    """
    by_date: dict[str, List[Measurement]] = {}
    for m in measurements:
        date_key = _to_utc_naive(m.timestamp).date().isoformat()
        by_date.setdefault(date_key, []).append(m)

    daily: List[DailyEnergy] = []
    for date_key in sorted(by_date):
        day_measurements = by_date[date_key]
        powers = [m.power_w for m in day_measurements]
        ordered = sorted(day_measurements, key=lambda m: _to_utc_naive(m.timestamp))
        total_wh = integrate_energy(ordered)
        start_ts = _to_utc_naive(ordered[0].timestamp)
        end_ts = _to_utc_naive(ordered[-1].timestamp)
        duration_hours = max((end_ts - start_ts).total_seconds() / 3600.0, 0.0)

        daily.append(
            DailyEnergy(
                date=date_key,
                energy_wh=total_wh,
                min_power_w=min(powers),
                max_power_w=max(powers),
                avg_power_w=sum(powers) / len(powers),
                sample_count=len(powers),
            )
        )
    return daily
