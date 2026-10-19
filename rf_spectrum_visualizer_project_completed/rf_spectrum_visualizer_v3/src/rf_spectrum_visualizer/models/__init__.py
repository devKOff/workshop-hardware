"""Shared channel model for RF Spectrum Visualizer V3.

Provides consistent channel-to-frequency mapping, validation, and
channel information across all three tools (Live Spectrum, Start Analysis,
Blocker). Consistent with both V3 and V6 source implementations.

Frequency mapping: frequency_mhz = 2400 + channel_number
Channel range: 0-125 (126 channels total)
"""

from .channel import channel_to_frequency, frequency_to_channel, validate_channel, get_all_channels, ChannelInfo, format_channel, parse_channel_input, get_wifi_overlap_channels, verify_all_mappings, verify_boundary_channels, verify_key_channels