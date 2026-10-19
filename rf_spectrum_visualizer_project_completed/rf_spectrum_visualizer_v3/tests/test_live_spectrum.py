"""Tests for Phase 2 — Live Spectrum integration.

Covers channel boundaries, frequency calculations, activity classifications,
scanner start/stop, duplicate-worker prevention, GUI responsiveness, and
error handling. Hardware tests are reported as unverified (no pyrf24 /
Raspberry Pi in this environment).
"""

from __future__ import annotations

import os
import sys
import time

# Tkinter needs the Tcl/Tk library located explicitly under pytest (the
# default computed path differs from a plain `python` run).
_PYTHON_DIR = os.path.dirname(sys.executable)
os.environ.setdefault("TCL_LIBRARY", os.path.join(_PYTHON_DIR, "tcl", "tcl8.6"))
os.environ.setdefault("TK_LIBRARY", os.path.join(_PYTHON_DIR, "tcl", "tk8.6"))

import tkinter as tk

import pytest

# Make both the destination package and the read-only V3 source importable.
sys.path.insert(0, "rf_spectrum_visualizer_v3/src")
sys.path.insert(0, "v3")

from rf_spectrum_visualizer.exceptions import InvalidChannelError  # noqa: E402
from rf_spectrum_visualizer.models.channel import (  # noqa: E402
    channel_to_frequency,
    frequency_to_channel,
    validate_channel,
    CHANNEL_MIN,
    CHANNEL_MAX,
)
from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig  # noqa: E402
from scanner import ScannerThread, SpectrumData  # noqa: E402
from sim_radio import SimRadio  # noqa: E402
from exceptions import ScannerAlreadyRunningError, ScannerError  # noqa: E402

from rf_spectrum_visualizer.ui.live_spectrum import LiveSpectrumApp  # noqa: E402


# --------------------------------------------------------------------------- #
# Channel boundaries & frequency calculations                                 #
# --------------------------------------------------------------------------- #
class TestChannelMapping:
    def test_boundary_channels(self):
        assert channel_to_frequency(0) == 2400
        assert channel_to_frequency(1) == 2401
        assert channel_to_frequency(125) == 2525

    def test_all_126_channels(self):
        for ch in range(CHANNEL_MIN, CHANNEL_MAX + 1):
            assert channel_to_frequency(ch) == 2400 + ch
            assert frequency_to_channel(2400 + ch) == ch

    def test_out_of_range_channel_raises(self):
        with pytest.raises(InvalidChannelError):
            channel_to_frequency(-1)
        with pytest.raises(InvalidChannelError):
            channel_to_frequency(126)
        with pytest.raises(InvalidChannelError):
            validate_channel(-1)
        with pytest.raises(InvalidChannelError):
            validate_channel(126)

    def test_validate_channel_accepts_valid(self):
        validate_channel(0)
        validate_channel(125)
        validate_channel(63)


# --------------------------------------------------------------------------- #
# Activity classifications                                                    #
# --------------------------------------------------------------------------- #
class TestActivityClassification:
    @pytest.fixture
    def thresholds(self):
        return ThresholdConfig()

    def test_clear_moderate_busy_heavy(self, thresholds):
        assert thresholds.classify(0) == "Clear"
        assert thresholds.classify(24) == "Clear"
        assert thresholds.classify(25) == "Moderate"
        assert thresholds.classify(49) == "Moderate"
        assert thresholds.classify(50) == "Busy"
        assert thresholds.classify(74) == "Busy"
        assert thresholds.classify(75) == "Heavy Load"
        assert thresholds.classify(100) == "Heavy Load"

    def test_insufficient_data(self, thresholds):
        assert thresholds.classify(None) == "INSUFFICIENT DATA"


# --------------------------------------------------------------------------- #
# Scanner start/stop / duplicate prevention                                   #
# --------------------------------------------------------------------------- #
class TestScannerLifecycle:
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(0, 5),
            scan=ScanConfig(measurement_window=0.05, sampling_interval=0.005),
            thresholds=ThresholdConfig(),
        )

    def test_start_stop(self, config):
        sd = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=7)
        radio.initialize()
        scanner = ScannerThread(config, sd, radio)
        assert scanner.is_running() is False
        scanner.start()
        assert scanner.is_running() is True
        time.sleep(0.2)
        scanner.stop()
        assert scanner.is_running() is False
        radio.cleanup()

    def test_duplicate_start_raises(self, config):
        sd = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=7)
        radio.initialize()
        scanner = ScannerThread(config, sd, radio)
        scanner.start()
        with pytest.raises(ScannerAlreadyRunningError):
            scanner.start()
        scanner.stop()
        radio.cleanup()

    def test_all_channels_scanned_with_freq(self, config):
        sd = SpectrumData(config)
        radio = SimRadio(config.channel, config.scan, seed=7)
        radio.initialize()
        scanner = ScannerThread(config, sd, radio)
        scanner.start()
        time.sleep(0.3)
        scanner.stop()
        radio.cleanup()
        obs = sd.get_all_observations()
        assert set(obs.keys()) == {0, 1, 2, 3, 4, 5}
        for ch in range(6):
            o = obs[ch]
            assert o.frequency_mhz == 2400 + ch
            assert o.backend == "sim"
            assert o.data_sufficient is True

    def test_hardware_unavailable_no_fake_readings(self, config):
        """Hardware backend unavailable -> ScannerError, no observations."""
        config.default_backend = "hardware"
        sd = SpectrumData(config)
        sd.set_backend("hardware")
        # HardwareRadio raises ScannerError at start when pyrf24 is missing.
        scanner = ScannerThread(config, sd)
        with pytest.raises(ScannerError):
            scanner.start()
        assert scanner.is_running() is False
        assert len(sd.get_all_observations()) == 0


# --------------------------------------------------------------------------- #
# GUI responsiveness / updates                                                #
# --------------------------------------------------------------------------- #
class TestGuiResponsiveness:
    @pytest.fixture(scope="module")
    def app(self):
        # One Tk instance for the whole module: creating/destroying several
        # Tk interpreters in one pytest process is unreliable on Windows.
        app = LiveSpectrumApp(AppConfig(), backend="sim")
        yield app
        try:
            app._stop_scan()
        except Exception:
            pass

    def test_app_creates_and_updates_without_crash(self, app):
        app._stop_scan()
        app._start_scan()
        # Pump the Tk event loop while scanning to exercise the refresh path.
        t0 = time.time()
        while time.time() - t0 < 1.0:
            try:
                app._root.update()
            except tk.TclError:
                break
            time.sleep(0.02)
        app._stop_scan()
        obs = app._spectrum_data.get_all_observations()
        assert len(obs) == 126
        # Every channel has a frequency = 2400 + channel.
        for ch in range(126):
            assert obs[ch].frequency_mhz == 2400 + ch
            assert obs[ch].backend == "sim"

    def test_status_bar_reports_busiest_and_average(self, app):
        app._stop_scan()
        app._start_scan()
        status = ""
        t0 = time.time()
        while time.time() - t0 < 1.0:
            status = app._status_var.get()
            try:
                app._root.update()
            except tk.TclError:
                break
            time.sleep(0.02)
        app._stop_scan()
        assert "busiest" in status
        assert "avg activity" in status
        assert "Simulation" in status

    def test_switching_mode_while_stopped(self, app):
        app._stop_scan()
        app._mode_var.set("hardware")
        app._on_mode_change()
        assert app._backend == "hardware"
        app._mode_var.set("sim")
        app._on_mode_change()
        assert app._backend == "sim"
        app._mode_var.set("hardware")
        app._on_mode_change()
        assert app._backend == "hardware"
        app._mode_var.set("sim")
        app._on_mode_change()
        assert app._backend == "sim"
