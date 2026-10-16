"""Tests for channel validation and frequency calculation (pure utilities)."""

from __future__ import annotations

import pytest

from src.rf_spectrum_visualizer.utils.channel import (
    channel_to_frequency,
    frequency_to_channel,
    validate_channel,
)


class TestValidateChannel:
    def test_boundaries_are_valid(self):
        assert validate_channel(0) is True
        assert validate_channel(125) is True

    def test_mid_range_is_valid(self):
        assert validate_channel(37) is True
        assert validate_channel(64) is True

    def test_out_of_range_is_invalid(self):
        assert validate_channel(-1) is False
        assert validate_channel(126) is False
        assert validate_channel(1000) is False

    def test_non_integers_are_invalid(self):
        assert validate_channel(3.5) is False
        assert validate_channel("7") is False
        assert validate_channel(None) is False
        assert validate_channel(True) is False  # bool is not a channel


class TestChannelToFrequency:
    def test_formula(self):
        assert channel_to_frequency(0) == 2400
        assert channel_to_frequency(1) == 2401
        assert channel_to_frequency(125) == 2525

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            channel_to_frequency(-1)
        with pytest.raises(ValueError):
            channel_to_frequency(126)


class TestFrequencyToChannel:
    def test_roundtrip(self):
        for ch in (0, 1, 37, 125):
            assert frequency_to_channel(2400 + ch) == ch

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            frequency_to_channel(2399)
        with pytest.raises(ValueError):
            frequency_to_channel(2526)
