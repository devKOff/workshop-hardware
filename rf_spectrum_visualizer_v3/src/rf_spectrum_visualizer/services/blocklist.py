"""Blocklist service for RF Spectrum Visualizer V3.

Integrates V6's BlocklistManager as the persistent JSON-backed blocklist
service. Provides block/unblock operations, persistence across application
restarts, corrupt-storage recovery, and blocklist-aware recommendation
filtering.

The blocklist is a software-level exclusion feature. It must not claim to
physically stop transmissions by other devices. Blocked channels remain
visible in spectrum and historical measurements but are excluded from
recommendations.

Key design decisions:
- Single BlocklistManager instance shared across all three GUI tools.
- JSON file persistence with atomic writes and corrupt-storage recovery.
- Blocked channels excluded from recommendations but visible in measurements.
- Immediate updates to shared application state (no restart required).
- Channel validation (0-125) on all operations.
"""

import logging
import os
from typing import List, Optional, Dict, Any

from ..models.channel import validate_channel, CHANNEL_MIN, CHANNEL_MAX
from ..exceptions import BlocklistError, InvalidChannelError

# Import V6's BlocklistManager directly (original source, not modified)
from v6.blocklist_manager import BlocklistManager as V6BlocklistManager  # type: ignore
from v6.config import BlocklistConfig

logger = logging.getLogger("rf_visualizer.services.blocklist")


class BlocklistService:
    """Persistent JSON-backed blocklist management service.

    Wraps V6's BlocklistManager to provide a consistent interface across
    all three GUI tools (Live Spectrum, Start Analysis, Blocker).

    Responsibilities:
    - Accept channel numbers 0-125 with automatic frequency calculation.
    - Prevent duplicate entries (one entry per channel).
    - Persist changes across application restarts via JSON file.
    - Recover safely from invalid or corrupted storage.
    - Update shared state immediately (no restart required).
    - Exclude blocked channels from recommendations.
    - Keep blocked channels visible in spectrum and historical measurements.

    The blocklist file path defaults to "blocklist.json" in the application
    data directory. The file is created on first block operation if it does
    not exist.
    """

    def __init__(self, config_file_path: str = "blocklist.json"):
        """Initialize the blocklist service.

        Args:
            config_file_path: Path to the blocklist JSON file.
        """
        # Create a minimal BlocklistConfig with the desired file path
        self._config = BlocklistConfig(file_path=config_file_path)
        self._manager = V6BlocklistManager(self._config)

        logger.info(f"Blocklist service initialized, file: {config_file_path}")

    def block_channel(self, channel: int, reason: str = "User blocked") -> Any:
        """Add a channel to the blocklist.

        Args:
            channel: Channel number to block (0-125).
            reason: Reason for blocking (default: "User blocked").

        Returns:
            BlocklistEntry object with channel, frequency_mhz, blocked_at, reason.

        Raises:
            InvalidChannelError: If channel is out of range [0, 125].
            BlocklistError: If save fails.
        """
        validate_channel(channel)
        entry = self._manager.block_channel(channel, reason)
        logger.info(f"Channel {channel} ({entry.frequency_mhz} MHz) blocked: {entry.reason}")
        return entry

    def unblock_channel(self, channel: int) -> bool:
        """Remove a channel from the blocklist.

        Args:
            channel: Channel number to unblock (0-125).

        Returns:
            True if channel was blocked and removed, False if not blocked.

        Raises:
            InvalidChannelError: If channel is out of range [0, 125].
            BlocklistError: If save fails.
        """
        validate_channel(channel)
        result = self._manager.unblock_channel(channel)
        if result:
            logger.info(f"Channel {channel} unblocked")
        else:
            logger.debug(f"Channel {channel} was not blocked")
        return result

    def is_blocked(self, channel: int) -> bool:
        """Check if a channel is blocked.

        Args:
            channel: Channel number to check (0-125).

        Returns:
            True if blocked, False otherwise.

        Raises:
            InvalidChannelError: If channel is out of range [0, 125].
        """
        validate_channel(channel)
        return self._manager.is_blocked(channel)

    def get_blocked_channels(self) -> List[int]:
        """Get sorted list of blocked channel numbers.

        Returns:
            Sorted list of blocked channel numbers.
        """
        return self._manager.get_blocked_channels()

    def get_blocked_entries(self) -> List[Any]:
        """Get all blocklist entries sorted by channel.

        Returns:
            List of BlocklistEntry objects sorted by channel number.
        """
        return self._manager.get_blocked_entries()

    def get_entry(self, channel: int) -> Optional[Any]:
        """Get blocklist entry for a specific channel.

        Args:
            channel: Channel number to look up (0-125).

        Returns:
            BlocklistEntry if blocked, None otherwise.

        Raises:
            InvalidChannelError: If channel is out of range [0, 125].
        """
        validate_channel(channel)
        return self._manager.get_entry(channel)

    def clear(self) -> int:
        """Clear all blocked channels.

        Returns:
            Number of channels that were blocked and have been cleared.
        """
        return self._manager.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get blocklist statistics.

        Returns:
            Dictionary with total_blocked, channels list, file_path, last_modified.
        """
        return self._manager.get_stats()

    def reload(self) -> None:
        """Reload blocklist from disk.

        Useful if the blocklist file has been modified externally.
        """
        self._manager.reload()

    def get_blocked_count(self) -> int:
        """Get the number of currently blocked channels.

        Returns:
            Count of blocked channels.
        """
        return len(self.get_blocked_channels())

    def blocklist_exists(self) -> bool:
        """Check if the blocklist file exists.

        Returns:
            True if the blocklist JSON file exists.
        """
        return os.path.exists(self._config.file_path)

    def get_blocked_frequencies(self) -> List[int]:
        """Get frequencies of blocked channels.

        Returns:
            List of frequency values in MHz for blocked channels.
        """
        channels = self.get_blocked_channels()
        return [2400 + ch for ch in channels]

    def get_status_summary(self) -> Dict[str, Any]:
        """Get status summary for UI display.

        Returns:
            Dictionary with blocked count, channel list, persistence info.
        """
        return {
            "blocked_count": self.get_blocked_count(),
            "blocked_channels": self.get_blocked_channels(),
            "blocked_frequencies_mhz": self.get_blocked_frequencies(),
            "file_path": self._config.file_path,
            "file_exists": self.blocklist_exists(),
        }