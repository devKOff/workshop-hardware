"""Settings service: validation, defaults, persistence."""

from __future__ import annotations

from solar_monitor.database.dao import get_setting, set_setting


class SettingsError(ValueError):
    pass


def _positive_float(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise SettingsError(f"must be a number: {value!r}")
    if not f > 0:
        raise SettingsError(f"must be > 0: {value!r}")
    return f


def _nonnegative_float(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise SettingsError(f"must be a number: {value!r}")
    if not f >= 0:
        raise SettingsError(f"must be >= 0: {value!r}")
    return f


def _non_empty_str(value):
    s = str(value).strip()
    if not s:
        raise SettingsError("must not be empty")
    return s


def _choice(value, choices):
    s = str(value)
    if s not in choices:
        raise SettingsError(f"must be one of {choices}: {value!r}")
    return s


_DEFAULTS = {
    "sampling_interval_s": (2.0, _positive_float),
    "graph_history_seconds": (300.0, _positive_float),
    "graph_refresh_ms": (1000.0, _positive_float),
    "db_location": ("solar_measurements.db", _non_empty_str),
    "default_export_dir": ("exports", _non_empty_str),
    "sim_base_voltage_v": (5.5, _positive_float),
    "sim_noise_amplitude_v": (0.05, _nonnegative_float),
    "sensor_mode": ("simulated", lambda v: _choice(v, ("simulated", "hardware"))),
}


class SettingsService:
    def __init__(self, conn):
        self._conn = conn

    def get(self, key):
        if key not in _DEFAULTS:
            raise SettingsError(f"unknown setting: {key}")
        default, validator = _DEFAULTS[key]
        raw = get_setting(self._conn, key)
        if raw is None:
            return default
        try:
            return validator(raw)
        except SettingsError:
            return default

    def set(self, key, value):
        if key not in _DEFAULTS:
            raise SettingsError(f"unknown setting: {key}")
        _, validator = _DEFAULTS[key]
        converted = validator(value)
        set_setting(self._conn, key, converted)
        return converted

    def get_all(self):
        return {key: self.get(key) for key in _DEFAULTS}
