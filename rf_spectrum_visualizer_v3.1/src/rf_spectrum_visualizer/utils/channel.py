"""Channel validation and frequency helpers.

Pure functions with no hardware or backend dependencies.
"""

from __future__ import annotations

from ..constants import RF_CHANNEL_MAX, RF_CHANNEL_MIN, RF_BASE_FREQUENCY_MHZ


def validate_channel(channel: int) -> bool:
    """Return True if *channel* is an integer in [0, 125]."""
    if isinstance(channel, bool) or not isinstance(channel, int):
        return False
    return RF_CHANNEL_MIN <= channel <= RF_CHANNEL_MAX


def channel_to_frequency(channel: int) -> int:
    """Convert a channel number to its frequency in MHz.

    frequency(MHz) = 2400 + channel_number
    """
    if not validate_channel(channel):
        raise ValueError(
            f"Channel {channel!r} is out of range [{RF_CHANNEL_MIN}, {RF_CHANNEL_MAX}]"
        )
    return RF_BASE_FREQUENCY_MHZ + channel


def frequency_to_channel(frequency_mhz: int) -> int:
    """Convert a frequency in MHz back to a channel number."""
    channel = frequency_mhz - RF_BASE_FREQUENCY_MHZ
    if not validate_channel(channel):
        raise ValueError(
            f"Frequency {frequency_mhz} MHz does not map to a valid channel "
            f"[{RF_CHANNEL_MIN}, {RF_CHANNEL_MAX}]"
        )
    return channel
