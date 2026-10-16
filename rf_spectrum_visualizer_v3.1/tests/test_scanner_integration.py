"""Integration tests for Live Spectrum V3 scanner connection.

Tests use the simulation backend (no hardware required). Hardware tests are
reported as unverified when physical Raspberry Pi hardware is unavailable.
"""

from __future__ import annotations

import time

import pytest

from rf_spectrum_visualizer.config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig
from rf_spectrum_visualizer.v3_bridge import (
    ScannerThread,
    SpectrumData,
    ChannelObservation,
    hardware_available,
)


class TestScannerIntegration:
    def test_spectrum_data_creation(self):
        config = AppConfig.defaults()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        assert sd.get_backend() == "sim"
        assert sd.get_scan_count() == 0
        assert sd.get_all_observations() == {}

    def test_scanner_start_stop_sim(self, tk_root):
        config = AppConfig.defaults()
        config.default_backend = "sim"
        config.channel.start_channel = 0
        config.channel.end_channel = 5  # small range for fast test
        config.scan.measurement_window = 0.1
        config.scan.sampling_interval = 0.01

        sd = SpectrumData(config)
        sd.set_backend("sim")

        scanner = ScannerThread(
            config,
            sd,
            radio=None,
            on_observation=lambda obs: None,
            on_error=lambda e: None,
            on_scan_complete=lambda: None,
        )
        assert not scanner.is_running()

        scanner.start()
        assert scanner.is_running()

        # Let it scan a few channels
        time.sleep(0.3)

        observations = sd.get_all_observations()
        assert len(observations) > 0, "Scanner should have produced observations"

        # Verify observations have expected fields
        for ch, obs in observations.items():
            assert obs.channel == ch
            assert obs.frequency_mhz == 2400 + ch
            assert obs.backend == "sim"
            assert obs.status in (
                "Clear", "Moderate", "Busy", "Heavy Load",
                "INSUFFICIENT DATA", "SENSOR_ERROR",
            )

        scanner.shutdown()
        assert not scanner.is_running()

    def test_channel_boundaries(self):
        """All 126 channels (0-125) are valid."""
        from rf_spectrum_visualizer.utils.channel import validate_channel, channel_to_frequency
        assert validate_channel(0) is True
        assert validate_channel(125) is True
        assert validate_channel(-1) is False
        assert validate_channel(126) is False

    def test_frequency_calculation(self):
        """Frequency = 2400 + channel_number."""
        from rf_spectrum_visualizer.utils.channel import channel_to_frequency
        assert channel_to_frequency(0) == 2400
        assert channel_to_frequency(1) == 2401
        assert channel_to_frequency(6) == 2406  # Wi-Fi channel 1
        assert channel_to_frequency(11) == 2411  # Wi-Fi channel 2 (approx)
        assert channel_to_frequency(122) == 2522
        assert channel_to_frequency(125) == 2525

    def test_activity_classifications(self):
        """ThresholdConfig.classify returns correct labels."""
        config = AppConfig.defaults()
        thr = config.thresholds
        assert thr.classify(0) == "Clear"
        assert thr.classify(10) == "Clear"
        assert thr.classify(24) == "Clear"
        assert thr.classify(25) == "Moderate"
        assert thr.classify(49) == "Moderate"
        assert thr.classify(50) == "Busy"
        assert thr.classify(74) == "Busy"
        assert thr.classify(75) == "Heavy Load"
        assert thr.classify(100) == "Heavy Load"
        assert thr.classify(None) == "INSUFFICIENT DATA"

    def test_scanner_duplicate_start_raises(self):
        """Starting an already-running scanner raises ScannerAlreadyRunningError."""
        from rf_spectrum_visualizer.v3_bridge import ScannerAlreadyRunningError
        config = AppConfig.defaults()
        config.default_backend = "sim"
        config.channel.start_channel = 0
        config.channel.end_channel = 2
        config.scan.measurement_window = 0.1
        config.scan.sampling_interval = 0.01

        sd = SpectrumData(config)
        sd.set_backend("sim")

        scanner = ScannerThread(
            config, sd, radio=None,
            on_observation=lambda obs: None,
            on_error=lambda e: None,
            on_scan_complete=lambda: None,
        )
        scanner.start()
        try:
            with pytest.raises(ScannerAlreadyRunningError):
                scanner.start()
        finally:
            scanner.shutdown()

    def test_scanner_channel_range_0_to_125(self):
        """ScannerThread accepts channel range 0-125."""
        config = AppConfig.defaults()
        config.default_backend = "sim"
        config.channel.start_channel = 0
        config.channel.end_channel = 125
        config.scan.measurement_window = 0.05
        config.scan.sampling_interval = 0.01

        sd = SpectrumData(config)
        sd.set_backend("sim")

        scanner = ScannerThread(
            config, sd, radio=None,
            on_observation=lambda obs: None,
            on_error=lambda e: None,
            on_scan_complete=lambda: None,
        )
        scanner.start()
        time.sleep(0.2)
        observations = sd.get_all_observations()
        scanner.shutdown()

        # Should have scanned at least some channels
        assert len(observations) > 0
        # All observed channels should be in 0-125
        for ch in observations:
            assert 0 <= ch <= 125

    def test_hardware_availability_unverified(self):
        """Hardware availability is checked; on this machine it's expected to be False."""
        # On Windows without Raspberry Pi hardware, pyrf24 is not installed.
        # Hardware tests are reported as unverified, not failed.
        avail = hardware_available()
        assert isinstance(avail, bool)
        if not avail:
            pytest.skip("Hardware (pyrf24) not available — hardware tests unverified")

    def test_channel_observation_fields(self):
        """ChannelObservation has all expected fields."""
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=11,
            frequency_mhz=2411,
            backend="sim",
            valid_samples=100,
            rpd_positive=37,
            rpd_negative=63,
            activity_percentage=37.0,
            status="Moderate",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        assert obs.channel == 11
        assert obs.frequency_mhz == 2411
        assert obs.backend == "sim"
        assert obs.activity_percentage == 37.0
        assert obs.status == "Moderate"
        assert obs.data_sufficient is True

    def test_scan_cycle_count_increments(self):
        """Scan count increments after each full cycle."""
        config = AppConfig.defaults()
        config.default_backend = "sim"
        config.channel.start_channel = 0
        config.channel.end_channel = 3
        config.scan.measurement_window = 0.05
        config.scan.sampling_interval = 0.01

        sd = SpectrumData(config)
        sd.set_backend("sim")

        scanner = ScannerThread(
            config, sd, radio=None,
            on_observation=lambda obs: None,
            on_error=lambda e: None,
            on_scan_complete=lambda: None,
        )
        scanner.start()
        time.sleep(0.3)
        count_after = sd.get_scan_count()
        scanner.shutdown()

        assert count_after >= 1, "Scan count should increment after at least one cycle"
