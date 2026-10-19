"""Tests for application configuration (app/config.py)."""

import os
import tempfile

import pytest

from app.config import (
    DEFAULTS,
    Config,
    _coerce_types,
    _read_env_file,
    _read_json_file,
    load_config,
)


def test_defaults_contain_expected_keys():
    assert DEFAULTS["SAMPLING_INTERVAL_SECONDS"] == 2
    assert DEFAULTS["SENSOR_MODE"] == "simulation"
    assert DEFAULTS["INA219_I2C_ADDRESS"] == 0x40


def test_load_config_defaults(tmp_path, monkeypatch):
    # Point at empty .env / config.json so only defaults apply.
    env_file = tmp_path / ".env"
    json_file = tmp_path / "config.json"
    env_file.write_text("")
    json_file.write_text("{}")
    monkeypatch.chdir(tmp_path)
    values = load_config(env_file=".env", json_file="config.json")
    assert values["SENSOR_MODE"] == "simulation"
    assert values["SAMPLING_INTERVAL_SECONDS"] == 2
    assert values["PORT"] == 5000


def test_env_file_parsing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "SENSOR_MODE=hardware\n"
        'SAMPLING_INTERVAL_SECONDS="5"\n'
        "INA219_I2C_ADDRESS=0x41\n"
        "DEBUG=true\n"
        "INA219_SHUNT_OHMS=0.2\n"
        "PORT=8080\n"
    )
    json_file = tmp_path / "config.json"
    json_file.write_text("{}")
    monkeypatch.chdir(tmp_path)
    values = load_config(env_file=".env", json_file="config.json")
    coerced = _coerce_types(values)
    assert coerced["SENSOR_MODE"] == "hardware"
    assert coerced["SAMPLING_INTERVAL_SECONDS"] == 5
    assert coerced["INA219_I2C_ADDRESS"] == 0x41
    assert coerced["DEBUG"] is True
    assert coerced["INA219_SHUNT_OHMS"] == 0.2
    assert coerced["PORT"] == 8080


def test_env_var_overrides_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SENSOR_MODE=simulation\n")
    json_file = tmp_path / "config.json"
    json_file.write_text("{}")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENSOR_MODE", "hardware")
    monkeypatch.setenv("SAMPLING_INTERVAL_SECONDS", "9")
    values = load_config(env_file=".env", json_file="config.json")
    assert values["SENSOR_MODE"] == "hardware"
    assert values["SAMPLING_INTERVAL_SECONDS"] == 9


def test_config_validate_ok():
    cfg = Config.from_dict(load_config())
    cfg.validate()  # should not raise


def test_config_validate_bad_mode():
    cfg = Config.from_dict(load_config())
    cfg.sensor_mode = "invalid"
    with pytest.raises(ValueError):
        cfg.validate()


def test_config_validate_bad_interval():
    cfg = Config.from_dict(load_config())
    cfg.sampling_interval_seconds = 0.1
    with pytest.raises(ValueError):
        cfg.validate()


def test_config_validate_bad_port():
    cfg = Config.from_dict(load_config())
    cfg.port = 99999
    with pytest.raises(ValueError):
        cfg.validate()


def test_config_from_dict_coerces_hex_address():
    values = dict(DEFAULTS)
    values["INA219_I2C_ADDRESS"] = "0x41"
    cfg = Config.from_dict(values)
    assert cfg.ina219_i2c_address == 0x41


def test_config_from_dict_coerces_int_address():
    values = dict(DEFAULTS)
    values["INA219_I2C_ADDRESS"] = 0x41
    cfg = Config.from_dict(values)
    assert cfg.ina219_i2c_address == 0x41
