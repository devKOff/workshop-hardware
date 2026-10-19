"""Tests for the simulation backend."""
from __future__ import annotations

import math

from sensor.simulation import SimulatedSensor


def test_simulation_labeled():
    sim = SimulatedSensor()
    assert sim.mode == "simulated"
    assert sim.is_available()


def test_reading_fields():
    sim = SimulatedSensor()
    r = sim.read()
    assert r.mode == "simulated"
    assert r.status == "ok"
    assert r.error is None
    assert r.voltage_v >= 0
    assert r.current_a >= 0
    assert r.power_register_w is not None
    assert r.power_register_w >= 0


def test_no_impossible_values():
    sim = SimulatedSensor()
    for _ in range(50):
        r = sim.read()
        assert r.voltage_v >= 0
        assert r.current_a >= 0


def test_fault_mode():
    sim = SimulatedSensor(fault=True)
    r = sim.read()
    assert r.status == "fault"
    assert r.error is not None


def test_no_pi_imports():
    import sensor.simulation as mod
    text = open(mod.__file__, encoding="utf-8").read()
    for forbidden in ("board", "busio", "adafruit", "rpi", "gpiozero"):
        assert forbidden not in text.lower()