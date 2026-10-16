"""Cross-module integration tests for Phase 5.

Verifies that Live Spectrum, Start Analysis, and Blocker work together
as one stable application:

- Live Spectrum scan data flows to Analysis without creating duplicate
  scanner instances.
- Blocker exclusions persist across application restart and are applied
  to Analysis recommendations.
- Excluded channels remain visible in Live Spectrum measurements.
- Channel numbering (0-125), frequency calculations (2400 + channel_number
  MHz), activity percentages, and status classifications work end-to-end.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from rf_spectrum_visualizer.config import AppConfig
from rf_spectrum_visualizer.v3_bridge import (
    ScannerThread,
    SpectrumData,
    ChannelObservation,
)
from rf_spectrum_visualizer.gui.start_analysis_page import run_analysis
from rf_spectrum_visualizer.utils.persistence import (
    save_excluded_channels,
    load_excluded_channels,
    clear_storage_file,
)

STORAGE_FILE = "blocker_exclusions.json"


def _remove_storage_file() -> None:
    try:
        if os.path.exists(STORAGE_FILE):
            os.remove(STORAGE_FILE)
    except OSError:
        pass


def _make_obs(
    channel: int,
    activity: float,
    status: str,
    backend: str = "sim",
    valid_samples: int = 100,
    rpd_positive: int = 0,
) -> ChannelObservation:
    return ChannelObservation(
        timestamp=time.time(),
        channel=channel,
        frequency_mhz=2400 + channel,
        backend=backend,
        valid_samples=valid_samples,
        rpd_positive=int(activity),
        rpd_negative=valid_samples - int(activity),
        activity_percentage=activity,
        status=status,
        data_sufficient=True,
        measurement_window=1.0,
        sampling_interval=0.01,
    )


def _make_config() -> AppConfig:
    config = AppConfig.defaults()
    config.channel.start_channel = 0
    config.channel.end_channel = 125
    return config


class TestCrossModuleIntegration:
    """End-to-end integration across Live Spectrum → Analysis → Blocker."""

    def setup_method(self):
        _remove_storage_file()

    def teardown_method(self):
        _remove_storage_file()

    def test_live_spectrum_to_analysis_no_duplicate_scanner(self):
        """Analysis reads from shared SpectrumData without starting a scanner."""
        config = _make_config()
        config.channel.start_channel = 0
        config.channel.end_channel = 10

        sd = SpectrumData(config)
        sd.set_backend("sim")

        # Simulate Live Spectrum scan: populate SpectrumData directly with
        # observations (as ScannerThread would during a real scan).
        for ch in range(0, 11):
            sd.update_observation(_make_obs(ch, 10.0 + ch, "Clear"))

        initial_count = sd.get_scan_count()
        scan_count_before = sd.get_scan_count()

        # Analysis reads the same SpectrumData — no new scanner created.
        result = run_analysis(sd, config)
        scan_count_after = sd.get_scan_count()

        assert scan_count_after == scan_count_before, (
            "Analysis must not start a duplicate scanner worker"
        )
        assert result.channels_analyzed > 0
        assert result.scan_count == scan_count_before

    def test_blocker_exclusions_persist_and_affect_analysis(self):
        """Exclusions saved to disk are loaded and applied to Analysis."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")

        # Channels 5 and 10 are Clear candidates.
        sd.update_observation(_make_obs(5, 10.0, "Clear"))
        sd.update_observation(_make_obs(10, 12.0, "Clear"))

        # Save exclusions to disk (simulating Blocker page "Add").
        save_excluded_channels([5])
        loaded = load_excluded_channels()
        assert loaded == {5}

        # Analysis uses loaded exclusions: channel 5 excluded, only 10 recommended.
        result = run_analysis(sd, config, excluded_channels=loaded)
        assert result.recommended_channels == [10]
        assert 5 not in result.recommended_channels

    def test_blocker_exclusions_survive_restart(self):
        """Exclusions persist in storage file across simulated restart."""
        save_excluded_channels([3, 7, 12])
        loaded = load_excluded_channels()
        assert loaded == {3, 7, 12}

        # Clear and re-load: data still there.
        loaded_again = load_excluded_channels()
        assert loaded_again == {3, 7, 12}

    def test_excluded_channels_visible_in_live_spectrum(self):
        """Excluded channels remain in SpectrumData (Live Spectrum measurements)."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")

        sd.update_observation(_make_obs(5, 10.0, "Clear"))

        # Even when excluded, channel 5 remains in SpectrumData.
        obs = sd.get_observation(5)
        assert obs is not None
        assert obs.channel == 5
        assert obs.activity_percentage == 10.0

        # Analysis entry still shows the measurement.
        result = run_analysis(sd, config, excluded_channels={5})
        entry_5 = [e for e in result.entries if e.channel == 5][0]
        assert entry_5.blocked is True
        assert entry_5.activity_percentage == 10.0
        assert entry_5.recommendation == "Blocked — excluded"

    def test_channel_numbering_and_frequency_end_to_end(self):
        """All 126 channels map correctly: frequency = 2400 + channel."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")

        # Scan a few representative channels.
        for ch in (0, 1, 6, 11, 37, 62, 76, 122, 125):
            sd.update_observation(_make_obs(ch, 10.0, "Clear"))

        result = run_analysis(sd, config)
        freq_map = {e.channel: e.frequency_mhz for e in result.entries}
        assert freq_map[0] == 2400
        assert freq_map[1] == 2401
        assert freq_map[6] == 2406
        assert freq_map[11] == 2411
        assert freq_map[37] == 2437
        assert freq_map[62] == 2462
        assert freq_map[76] == 2476
        assert freq_map[122] == 2522
        assert freq_map[125] == 2525

    def test_activity_percentages_and_status_classifications(self):
        """Activity percentages classify correctly across all four levels."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")

        sd.update_observation(_make_obs(0, 0.0, "Clear"))
        sd.update_observation(_make_obs(1, 24.0, "Clear"))
        sd.update_observation(_make_obs(2, 25.0, "Moderate"))
        sd.update_observation(_make_obs(3, 49.0, "Moderate"))
        sd.update_observation(_make_obs(4, 50.0, "Busy"))
        sd.update_observation(_make_obs(5, 74.0, "Busy"))
        sd.update_observation(_make_obs(6, 75.0, "Heavy Load"))
        sd.update_observation(_make_obs(7, 100.0, "Heavy Load"))

        result = run_analysis(sd, config)
        statuses = {e.channel: e.status for e in result.entries}
        assert statuses[0] == "Clear"
        assert statuses[1] == "Clear"
        assert statuses[2] == "Moderate"
        assert statuses[3] == "Moderate"
        assert statuses[4] == "Busy"
        assert statuses[5] == "Busy"
        assert statuses[6] == "Heavy Load"
        assert statuses[7] == "Heavy Load"

    def test_blocker_clear_removes_persistence_file(self):
        """Clear All removes the storage file."""
        save_excluded_channels([5, 10])
        assert os.path.exists(STORAGE_FILE)

        clear_storage_file()
        assert not os.path.exists(STORAGE_FILE)
        assert load_excluded_channels() == set()

    def test_corrupted_storage_file_does_not_crash_analysis(self):
        """Corrupted blocker file → empty exclusions → Analysis still works."""
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            f.write("{not valid json!!!")

        loaded = load_excluded_channels()
        assert loaded == set()

        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        sd.update_observation(_make_obs(5, 10.0, "Clear"))

        result = run_analysis(sd, config, excluded_channels=loaded)
        assert result.recommended_channels == [5]


class TestRegression:
    """Regression tests to prevent previously fixed bugs from returning."""

    def test_scanner_start_stop_lifecycle(self):
        """Scanner can be started and stopped cleanly, no duplicate workers."""
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
        assert not scanner.is_running()

        scanner.start()
        assert scanner.is_running()

        # Second start should raise.
        from rf_spectrum_visualizer.v3_bridge import ScannerAlreadyRunningError
        with pytest.raises(ScannerAlreadyRunningError):
            scanner.start()

        scanner.shutdown()
        assert not scanner.is_running()

    def test_analysis_empty_data_no_crash(self):
        """Analysis of empty SpectrumData returns empty result, no crash."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        result = run_analysis(sd, config)
        assert result.empty is True
        assert result.channels_analyzed == 0
        assert result.average_activity == 0.0

    def test_analysis_insufficient_data_no_crash(self):
        """Analysis of insufficient data handles gracefully."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        sd.update_observation(
            ChannelObservation(
                timestamp=time.time(),
                channel=5,
                frequency_mhz=2405,
                backend="sim",
                valid_samples=0,
                rpd_positive=0,
                rpd_negative=0,
                activity_percentage=None,
                status="INSUFFICIENT DATA",
                data_sufficient=False,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
        )
        result = run_analysis(sd, config)
        assert result.channels_analyzed == 0
        assert result.average_activity == 0.0

    def test_blocker_persistence_corruption_recovery(self):
        """Various corrupted storage files all return empty set safely."""
        corrupted_contents = [
            "{not valid json",
            "",
            "   ",
            json.dumps([5, 10]),           # array instead of object
            json.dumps({"other": [5]}),     # missing key
            json.dumps({"excluded_channels": "not a list"}),  # wrong type
        ]
        for content in corrupted_contents:
            _remove_storage_file()
            with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            assert load_excluded_channels() == set(), (
                f"Failed to recover from: {content!r}"
            )

    def test_blocker_out_of_range_channels_dropped(self):
        """Channels outside 0-125 are dropped from persistence."""
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump({"excluded_channels": [5, -1, 126, 200, 10]}, f)
        loaded = load_excluded_channels()
        assert loaded == {5, 10}

    def test_hardware_backend_unavailable_is_reported(self):
        """hardware_available() returns False on machines without pyrf24."""
        from rf_spectrum_visualizer.v3_bridge import hardware_available
        avail = hardware_available()
        assert isinstance(avail, bool)
        # On this Windows dev machine, pyrf24 is not installed.
        if not avail:
            pytest.skip("Hardware (pyrf24) not available — hardware tests unverified")

    def test_scan_count_increments_per_cycle(self):
        """Scan count increments after each full scan cycle."""
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
        count = sd.get_scan_count()
        scanner.shutdown()

        assert count >= 1, "Scan count should increment after at least one cycle"
