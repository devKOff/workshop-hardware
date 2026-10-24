"""Application configuration.

Configuration is resolved in the following priority order (highest first):
  1. Environment variables (e.g. SENSOR_MODE=hardware)
  2. config.json (JSON file on disk)
  3. .env file (simple KEY=VALUE pairs)
  4. Built-in defaults

Use `config.example.json` and `.env.example` as templates. Never commit
`config.json` or `.env` because they may contain local secrets/paths.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "SENSOR_MODE": "simulation",
    "SAMPLING_INTERVAL_SECONDS": 2,
    "INA219_I2C_ADDRESS": 0x40,
    "INA219_SHUNT_OHMS": 0.1,
    "INA219_MAX_EXPECTED_AMPS": 0.5,
    "DATABASE_PATH": "solar_monitor.db",
    "HOST": "0.0.0.0",
    "PORT": 5000,
    "DEBUG": False,
    "LOG_LEVEL": "INFO",
    "SECRET_KEY": "dev-secret-change-me",
}

# Keys parsed as integers.
_INT_KEYS = {
    "SAMPLING_INTERVAL_SECONDS",
    "INA219_I2C_ADDRESS",
    "PORT",
}

# Keys parsed as booleans.
_BOOL_KEYS = {"DEBUG"}

# Keys parsed as floats.
_FLOAT_KEYS = {"INA219_SHUNT_OHMS", "INA219_MAX_EXPECTED_AMPS"}

# Minimum allowed sampling interval (seconds) to avoid over-sampling.
MIN_SAMPLING_INTERVAL_SECONDS = 0.5


def _read_env_file(path: str) -> Dict[str, str]:
    """Parse a simple .env file into a dict of strings."""
    values: Dict[str, str] = {}
    if not os.path.exists(path):
        return values
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    values[key] = value
    except OSError:
        # A missing or unreadable .env file is not fatal.
        return values
    return values


def _read_json_file(path: str) -> Dict[str, Any]:
    """Parse a JSON config file into a dict."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def load_config(env_file: str = ".env", json_file: str = "config.json") -> Dict[str, Any]:
    """Load merged configuration from .env, config.json, and environment vars."""
    merged: Dict[str, Any] = dict(DEFAULTS)

    # Layer 1: .env file
    merged.update(_read_env_file(env_file))

    # Layer 2: config.json
    merged.update(_read_json_file(json_file))

    # Layer 3: environment variables (highest priority)
    for key, value in DEFAULTS.items():
        env_value = os.environ.get(key)
        if env_value is not None:
            merged[key] = env_value

    return _coerce_types(merged)


def _coerce_types(values: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce configuration values to their expected Python types."""
    coerced: Dict[str, Any] = {}
    for key, value in values.items():
        if key in _INT_KEYS:
            try:
                if isinstance(value, str):
                    coerced[key] = int(value, 0)  # base 0 handles 0x40 hex strings
                else:
                    coerced[key] = int(value)
            except (TypeError, ValueError):
                coerced[key] = int(DEFAULTS[key])
        elif key in _BOOL_KEYS:
            coerced[key] = str(value).strip().lower() in {"1", "true", "yes", "on"}
        elif key in _FLOAT_KEYS:
            try:
                coerced[key] = float(value)
            except (TypeError, ValueError):
                coerced[key] = float(DEFAULTS[key])
        else:
            coerced[key] = value
    return coerced


@dataclass
class Config:
    """Strongly-typed application configuration."""

    sensor_mode: str
    sampling_interval_seconds: float
    ina219_i2c_address: int
    ina219_shunt_ohms: float
    ina219_max_expected_amps: float
    database_path: str
    host: str
    port: int
    debug: bool
    log_level: str
    secret_key: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _to_int(value: Any) -> int:
        if isinstance(value, str):
            return int(value, 0)  # base 0 handles 0x40 hex strings
        return int(value)

    @classmethod
    def from_dict(cls, values: Dict[str, Any]) -> "Config":
        return cls(
            sensor_mode=str(values.get("SENSOR_MODE", DEFAULTS["SENSOR_MODE"])),
            sampling_interval_seconds=float(values.get(
                "SAMPLING_INTERVAL_SECONDS", DEFAULTS["SAMPLING_INTERVAL_SECONDS"])),
            ina219_i2c_address=cls._to_int(
                values.get("INA219_I2C_ADDRESS", DEFAULTS["INA219_I2C_ADDRESS"])
            ),
            ina219_shunt_ohms=float(values.get("INA219_SHUNT_OHMS", DEFAULTS["INA219_SHUNT_OHMS"])),
            ina219_max_expected_amps=float(values.get(
                "INA219_MAX_EXPECTED_AMPS", DEFAULTS["INA219_MAX_EXPECTED_AMPS"])),
            database_path=str(values.get("DATABASE_PATH", DEFAULTS["DATABASE_PATH"])),
            host=str(values.get("HOST", DEFAULTS["HOST"])),
            port=int(values.get("PORT", DEFAULTS["PORT"])),
            debug=bool(values.get("DEBUG", DEFAULTS["DEBUG"])),
            log_level=str(values.get("LOG_LEVEL", DEFAULTS["LOG_LEVEL"])),
            secret_key=str(values.get("SECRET_KEY", DEFAULTS["SECRET_KEY"])),
            raw=values,
        )

    def validate(self) -> None:
        """Validate configuration values; raise ValueError on problems."""
        if self.sensor_mode not in {"simulation", "hardware"}:
            raise ValueError(
                f"Invalid SENSOR_MODE '{self.sensor_mode}'; "
                "expected 'simulation' or 'hardware'")
        if self.sampling_interval_seconds < MIN_SAMPLING_INTERVAL_SECONDS:
            raise ValueError(
                f"SAMPLING_INTERVAL_SECONDS must be >= "
                f"{MIN_SAMPLING_INTERVAL_SECONDS}, got {self.sampling_interval_seconds}")
        if self.ina219_shunt_ohms <= 0:
            raise ValueError("INA219_SHUNT_OHMS must be positive")
        if self.ina219_max_expected_amps <= 0:
            raise ValueError("INA219_MAX_EXPECTED_AMPS must be positive")
        if not (1 <= self.port <= 65535):
            raise ValueError(f"PORT must be between 1 and 65535, got {self.port}")
        if not self.database_path:
            raise ValueError("DATABASE_PATH must not be empty")
