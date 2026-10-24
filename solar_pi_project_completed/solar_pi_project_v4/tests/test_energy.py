"""Tests for the trapezoidal energy integrator."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from measurement.energy import EnergyIntegrator, IntegrationState


def _iso(dt):
    return dt.isoformat()


def test_integrates_constant_power():
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    integ = EnergyIntegrator(sampling_interval_s=10.0, max_gap_multiplier=5.0)
    assert integ.add(_iso(base), 100.0) is None
    inc = integ.add(_iso(base + timedelta(seconds=10)), 100.0)
    assert abs(inc - 100.0 * 10 / 3600.0) < 1e-9


def test_irregular_intervals():
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    integ = EnergyIntegrator(sampling_interval_s=10.0, max_gap_multiplier=5.0)
    integ.add(_iso(base), 100.0)
    inc = integ.add(_iso(base + timedelta(seconds=30)), 100.0)
    assert abs(inc - 100.0 * 30 / 3600.0) < 1e-9


def test_gap_too_large_skipped():
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    integ = EnergyIntegrator(sampling_interval_s=10.0, max_gap_multiplier=5.0)
    integ.add(_iso(base), 100.0)
    assert integ.add(_iso(base + timedelta(seconds=60)), 100.0) is None
    assert integ.state.gaps_skipped == 1
    inc2 = integ.add(_iso(base + timedelta(seconds=70)), 100.0)
    assert inc2 is not None
    assert abs(inc2 - 100.0 * 10 / 3600.0) < 1e-9


def test_invalid_sample_breaks_chain():
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    integ = EnergyIntegrator(sampling_interval_s=10.0, max_gap_multiplier=5.0)
    integ.add(_iso(base), 100.0)
    assert integ.add(_iso(base + timedelta(seconds=10)), None) is None
    assert integ.add(_iso(base + timedelta(seconds=20)), 100.0) is None


def test_midnight_reset():
    base = datetime(2026, 1, 1, 23, 59, 50, tzinfo=timezone.utc)
    integ = EnergyIntegrator(sampling_interval_s=10.0, max_gap_multiplier=5.0)
    integ.add(_iso(base), 1000.0)
    inc = integ.add(_iso(base + timedelta(seconds=10)), 1000.0)
    assert inc is not None
    assert integ.state.last_day == "2026-01-02"


def test_non_monotonic_timestamp_restarts():
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    integ = EnergyIntegrator(sampling_interval_s=10.0, max_gap_multiplier=5.0)
    integ.add(_iso(base), 100.0)
    integ.add(_iso(base + timedelta(seconds=10)), 100.0)
    assert integ.add(_iso(base), 100.0) is None


def test_state_persist_roundtrip():
    state = IntegrationState(total_energy_wh=12.5, daily_energy_wh=3.0, gaps_skipped=2)
    state2 = IntegrationState.from_dict(state.to_dict())
    assert state2.total_energy_wh == 12.5
    assert state2.daily_energy_wh == 3.0
    assert state2.gaps_skipped == 2


def test_zero_power_integrates():
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    integ = EnergyIntegrator(sampling_interval_s=10.0, max_gap_multiplier=5.0)
    integ.add(_iso(base), 100.0)
    inc = integ.add(_iso(base + timedelta(seconds=10)), 0.0)
    assert abs(inc - 50.0 * 10 / 3600.0) < 1e-9