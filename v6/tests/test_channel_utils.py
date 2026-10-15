"""Tests for channel_utils module."""

import pytest
from v6.channel_utils import (
    channel_to_frequency,
    frequency_to_channel,
    validate_channel,
    validate_channel_list,
    get_all_channels,
    get_channels_in_range,
    format_channel,
    parse_channel_input,
    get_wifi_overlap_channels,
    ChannelInfo,
)
from v6.config import ChannelConfig
from v6.exceptions import InvalidChannelError


class TestChannelToFrequency:
    def test_valid_channels(self):
        assert channel_to_frequency(0) == 2400
        assert channel_to_frequency(1) == 2401
        assert channel_to_frequency(125) == 2525
        assert channel_to_frequency(122) == 2522
    
    def test_invalid_channels(self):
        with pytest.raises(InvalidChannelError):
            channel_to_frequency(-1)
        with pytest.raises(InvalidChannelError):
            channel_to_frequency(126)
        with pytest.raises(InvalidChannelError):
            channel_to_frequency(1000)


class TestFrequencyToChannel:
    def test_valid_frequencies(self):
        assert frequency_to_channel(2400) == 0
        assert frequency_to_channel(2401) == 1
        assert frequency_to_channel(2525) == 125
        assert frequency_to_channel(2522) == 122
    
    def test_invalid_frequencies(self):
        with pytest.raises(InvalidChannelError):
            frequency_to_channel(2399)
        with pytest.raises(InvalidChannelError):
            frequency_to_channel(2526)
        with pytest.raises(InvalidChannelError):
            frequency_to_channel(3000)


class TestValidateChannel:
    def test_valid(self):
        validate_channel(0)
        validate_channel(125)
        validate_channel(62)
    
    def test_invalid(self):
        with pytest.raises(InvalidChannelError):
            validate_channel(-1)
        with pytest.raises(InvalidChannelError):
            validate_channel(126)


class TestValidateChannelList:
    def test_valid_list(self):
        result = validate_channel_list([0, 1, 125, 62])
        assert result == [0, 1, 125, 62]
    
    def test_invalid_list(self):
        with pytest.raises(InvalidChannelError):
            validate_channel_list([0, 126])
        with pytest.raises(InvalidChannelError):
            validate_channel_list([-1, 5])


class TestGetAllChannels:
    def test_returns_126_channels(self):
        channels = get_all_channels()
        assert len(channels) == 126
        assert channels[0].channel == 0
        assert channels[0].frequency_mhz == 2400
        assert channels[-1].channel == 125
        assert channels[-1].frequency_mhz == 2525


class TestGetChannelsInRange:
    def test_full_range(self):
        config = ChannelConfig(0, 125)
        channels = get_channels_in_range(config)
        assert len(channels) == 126
    
    def test_partial_range(self):
        config = ChannelConfig(10, 20)
        channels = get_channels_in_range(config)
        assert len(channels) == 11
        assert channels[0].channel == 10
        assert channels[-1].channel == 20


class TestFormatChannel:
    def test_with_freq(self):
        assert format_channel(0) == "Ch   0 (2400 MHz)"
        assert format_channel(122) == "Ch 122 (2522 MHz)"
        assert format_channel(125) == "Ch 125 (2525 MHz)"
    
    def test_without_freq(self):
        assert format_channel(0, include_freq=False) == "Ch   0"


class TestParseChannelInput:
    def test_plain_number(self):
        assert parse_channel_input("122") == 122
        assert parse_channel_input("  122  ") == 122
    
    def test_with_ch_prefix(self):
        assert parse_channel_input("Ch 122") == 122
        assert parse_channel_input("CH 122") == 122
        assert parse_channel_input("ch122") == 122
    
    def test_frequency(self):
        assert parse_channel_input("2522 MHz") == 122
        assert parse_channel_input("2522MHz") == 122
        assert parse_channel_input("  2522  MHz  ") == 122
    
    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_channel_input("abc")
        with pytest.raises(InvalidChannelError):
            parse_channel_input("2526 MHz")  # 2526 - 2400 = 126, out of range
        with pytest.raises(InvalidChannelError):
            parse_channel_input("126")


class TestGetWifiOverlapChannels:
    def test_returns_wifi_channels(self):
        overlaps = get_wifi_overlap_channels()
        assert len(overlaps) > 0
        # Check known WiFi channels
        channels = [c for c, _, _ in overlaps]
        assert 12 in channels  # WiFi 1
        assert 37 in channels  # WiFi 6
        assert 62 in channels  # WiFi 11
    
    def test_format(self):
        overlaps = get_wifi_overlap_channels()
        for nrf_ch, wifi_ch, freq in overlaps:
            assert freq == 2400 + nrf_ch
            assert 1 <= wifi_ch <= 14


class TestChannelInfo:
    def test_valid(self):
        info = ChannelInfo(122, 2522)
        assert info.channel == 122
        assert info.frequency_mhz == 2522
    
    def test_invalid_freq(self):
        with pytest.raises(ValueError):
            ChannelInfo(122, 2523)
    
    def test_invalid_channel(self):
        with pytest.raises(ValueError):
            ChannelInfo(126, 2526)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
