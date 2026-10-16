"""Tests for Blocker → Analysis integration.

Verifies that:
- Excluded channels are omitted from Analysis recommendations
- Excluded channels remain present in scan measurements (Live Spectrum)
- Blocker persistence survives across Analysis runs
"""

from __future__ import annotations

import time

import pytest

from rf_spectrum_visualizer.config import AppConfig
from rf_spectrum_visualizer.v3_bridge import (
    SpectrumData,
    ChannelObservation,
)
from rf_spectrum_visualizer.gui.start_analysis_page import run_analysis


def _make_obs(channel: int, activity: float, status: str) -> ChannelObservation:
    return ChannelObservation(
        timestamp=time.time(),
        channel=channel,
        frequency_mhz=2400 + channel,
        backend="sim",
        valid_samples=100,
        rpd_positive=int(activity),
        rpd_negative=100 - int(activity),
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


class TestBlockerAnalysisIntegration:
    def test_excluded_channels_omitted_from_recommendations(self):
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")

        # Channels 5 and 10 are Clear (recommended). Channel 15 is Busy.
        sd.update_observation(_make_obs(5, 10.0, "Clear"))
        sd.update_observation(_make_obs(10, 12.0, "Clear"))
        sd.update_observation(_make_obs(15, 60.0, "Busy"))

        # Without exclusions: both 5 and 10 recommended.
        result_no_excl = run_analysis(sd, config)
        assert result_no_excl.recommended_channels == [5, 10]

        # With channel 5 excluded: only 10 recommended.
        result_excl = run_analysis(sd, config, excluded_channels={5})
        assert result_excl.recommended_channels == [10]

    def test_excluded_channels_remain_in_entries(self):
        """Excluded channels remain visible in results (not filtered out)."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        sd.update_observation(_make_obs(5, 10.0, "Clear"))

        result = run_analysis(sd, config, excluded_channels={5})
        # Channel 5 should still appear in entries.
        entry_5 = [e for e in result.entries if e.channel == 5]
        assert len(entry_5) == 1
        assert entry_5[0].blocked is True
        assert entry_5[0].recommendation == "Blocked — excluded"

    def test_blocked_channels_not_counted_as_recommended(self):
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        sd.update_observation(_make_obs(5, 10.0, "Clear"))
        sd.update_observation(_make_obs(10, 12.0, "Clear"))

        result = run_analysis(sd, config, excluded_channels={5, 10})
        assert result.recommended_channels == []
        assert result.channels_analyzed == 2  # still analyzed, just not recommended

    def test_persisted_blocker_affects_analysis(self, tmp_path, monkeypatch):
        """Simulate: blocker exclusions loaded from disk affect Analysis."""
        # This test verifies the flow: saved exclusions → loaded → analysis
        # excludes them. We test via run_analysis directly since the GUI
        # integration is covered by the BlockerPage loading exclusions on init.
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        sd.update_observation(_make_obs(3, 5.0, "Clear"))
        sd.update_observation(_make_obs(7, 8.0, "Clear"))

        # Simulate loaded exclusions from disk.
        saved_exclusions = {3}
        result = run_analysis(sd, config, excluded_channels=saved_exclusions)
        assert result.recommended_channels == [7]
        assert 3 not in result.recommended_channels

    def test_exclusion_does_not_affect_measurement_data(self):
        """Excluding a channel does not remove it from SpectrumData."""
        config = _make_config()
        sd = SpectrumData(config)
        sd.set_backend("sim")
        sd.update_observation(_make_obs(5, 10.0, "Clear"))

        # Channel 5 is in SpectrumData regardless of exclusion.
        obs = sd.get_observation(5)
        assert obs is not None
        assert obs.channel == 5
        assert obs.activity_percentage == 10.0

        # Analysis with exclusion still shows the entry.
        result = run_analysis(sd, config, excluded_channels={5})
        entry_5 = [e for e in result.entries if e.channel == 5][0]
        assert entry_5.activity_percentage == 10.0
        assert entry_5.status == "Clear"
        assert entry_5.blocked is True
