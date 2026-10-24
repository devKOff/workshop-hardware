"""Tests for energy calculations (app/services/energy_service.py)."""

from datetime import datetime, timedelta

import pytest

from app.models import Measurement
from app.services.energy_service import (
    compute_daily_energy,
    compute_summary,
    integrate_energy,
)


def _m(ts, power_w):
    return Measurement(ts, 6.0, power_w / 6.0 * 1000.0, power_w / 6.0, power_w)


# ------------------------------------------------------------------ #
# integrate_energy
# ------------------------------------------------------------------ #
def test_integrate_energy_regular_intervals():
    base = datetime(2026, 10, 19, 10, 0, 0)
    m = [
        _m(base, 2.0),      # 10:00
        _m(base + timedelta(minutes=10), 4.0),  # 10:10
        _m(base + timedelta(minutes=20), 6.0),  # 10:20
    ]
    # Trapezoids: (2+4)/2 * 1/6 + (4+6)/2 * 1/6 = 3/6 + 5/6 = 1.333 Wh
    wh = integrate_energy(m)
    assert wh == pytest.approx(1.3333, rel=1e-3)


def test_integrate_energy_irregular_intervals():
    base = datetime(2026, 10, 19, 10, 0, 0)
    m = [
        _m(base, 3.0),                            # 10:00
        _m(base + timedelta(minutes=2), 3.0),    # 10:02  (2 min)
        _m(base + timedelta(minutes=6), 3.0),    # 10:06  (4 min gap - missing samples)
        _m(base + timedelta(minutes=7), 3.0),    # 10:07  (1 min)
    ]
    wh = integrate_energy(m)
    expected = 3.0 * (2 + 4 + 1) / 60.0  # constant 3W over 7 minutes
    assert wh == pytest.approx(expected, rel=1e-6)


def test_integrate_energy_sorts_out_of_order_samples():
    base = datetime(2026, 10, 19, 10, 0, 0)
    m = [
        _m(base + timedelta(minutes=5), 5.0),
        _m(base, 5.0),  # out of order; gets sorted internally
    ]
    # Sorted into one 5-minute interval at 5 W = 5 * 5/60 Wh
    assert integrate_energy(m) == pytest.approx(5.0 * 5 / 60.0, rel=1e-6)


def test_integrate_energy_duplicate_timestamps_skipped():
    base = datetime(2026, 10, 19, 10, 0, 0)
    m = [
        _m(base, 5.0),
        _m(base, 9.0),  # same timestamp -> zero-duration interval skipped
    ]
    assert integrate_energy(m) == 0.0


def test_integrate_energy_fewer_than_two_samples():
    base = datetime(2026, 10, 19, 10, 0, 0)
    assert integrate_energy([]) == 0.0
    assert integrate_energy([_m(base, 5.0)]) == 0.0


# ------------------------------------------------------------------ #
# compute_summary
# ------------------------------------------------------------------ #
def test_compute_summary_empty():
    summary = compute_summary([])
    assert summary.sample_count == 0
    assert summary.total_energy_wh == 0.0
    assert summary.duration_hours == 0.0


def test_compute_summary_populated():
    base = datetime(2026, 10, 19, 10, 0, 0)
    m = [
        _m(base, 1.0),
        _m(base + timedelta(minutes=10), 3.0),
        _m(base + timedelta(minutes=20), 5.0),
    ]
    s = compute_summary(m)
    assert s.sample_count == 3
    assert s.min_power_w == 1.0
    assert s.max_power_w == 5.0
    assert s.avg_power_w == 3.0
    assert s.duration_hours == pytest.approx(20 / 60.0, rel=1e-6)


# ------------------------------------------------------------------ #
# compute_daily_energy (midnight rollover)
# ------------------------------------------------------------------ #
def test_daily_energy_midnight_rollover():
    # Two samples on 10/18 (both before midnight) and two on 10/19 (both
    # after midnight). Energy must NOT carry over between days.
    m = [
        _m(datetime(2026, 10, 18, 23, 58, 0), 4.0),
        _m(datetime(2026, 10, 18, 23, 59, 0), 4.0),
        _m(datetime(2026, 10, 19, 0, 1, 0), 4.0),
        _m(datetime(2026, 10, 19, 0, 2, 0), 4.0),
    ]
    daily = compute_daily_energy(m)
    assert len(daily) == 2
    d18 = daily[0]
    d19 = daily[1]
    assert d18.date == "2026-10-18"
    assert d19.date == "2026-10-19"
    # 1 minute at 4W each day = 4/60 Wh per day
    assert d18.energy_wh == pytest.approx(4.0 / 60.0, rel=1e-6)
    assert d19.energy_wh == pytest.approx(4.0 / 60.0, rel=1e-6)


def test_daily_energy_empty():
    assert compute_daily_energy([]) == []
