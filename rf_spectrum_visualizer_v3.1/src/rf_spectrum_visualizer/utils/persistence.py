"""Persistent storage for the Blocker exclusion list.

Reads and writes the set of excluded (software-blocked) channel numbers to a
local JSON configuration file. All operations are safe: missing files, empty
files, corrupted JSON, and invalid channel values are handled gracefully and
never crash the application.

The exclusion list represents software-level channel exclusion only — it
affects analysis recommendations, not RF transmissions or physical hardware.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Iterable, Set

from rf_spectrum_visualizer.constants import (
    RF_CHANNEL_MAX,
    RF_CHANNEL_MIN,
)
from rf_spectrum_visualizer.config import CONFIG_FILE

logger = logging.getLogger("rf_visualizer.utils.persistence")

# Storage file for the blocker exclusion list (sibling of CONFIG_FILE).
_BLOCKER_STORAGE_FILE = "blocker_exclusions.json"

# Key used inside the JSON file.
_CHANNELS_KEY = "excluded_channels"


def blocker_storage_path() -> str:
    """Return the filesystem path for the blocker exclusion storage file."""
    return _BLOCKER_STORAGE_FILE


def save_excluded_channels(channels: Iterable[int]) -> None:
    """Persist the excluded channel set to disk.

    Writes atomically (temp file then replace) so a crash mid-write never
    leaves a corrupted file. Invalid channels (outside 0-125) are silently
    dropped before writing.

    Args:
        channels: Iterable of channel numbers to persist.
    """
    valid_channels = sorted(
        {int(ch) for ch in channels
         if isinstance(ch, (int,)) and not isinstance(ch, bool)
         and RF_CHANNEL_MIN <= ch <= RF_CHANNEL_MAX}
    )
    data = {_CHANNELS_KEY: valid_channels}

    path = _BLOCKER_STORAGE_FILE
    # Atomic write: write to a temp file in the same directory, then replace.
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".blocker_", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
        logger.info("Saved %d excluded channel(s) to %s", len(valid_channels), path)
    except Exception as e:  # noqa: BLE001 - storage errors must not crash the GUI
        logger.error("Failed to save blocker exclusions: %s", e)
        # Clean up temp file if it exists.
        try:
            if os.path.exists(tmp_path):  # type: ignore[name-defined]
                os.remove(tmp_path)
        except Exception:  # noqa: BLE001
            pass


def load_excluded_channels() -> Set[int]:
    """Load the excluded channel set from disk.

    Handles gracefully:
    - Missing file -> returns empty set
    - Empty file -> returns empty set
    - Corrupted/invalid JSON -> returns empty set (logs error)
    - JSON without the expected key -> returns empty set
    - Channel values outside 0-125 or non-integers -> dropped

    Returns:
        A set of valid excluded channel numbers (0-125).
    """
    path = _BLOCKER_STORAGE_FILE
    if not os.path.exists(path):
        return set()

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception as e:  # noqa: BLE001 - storage errors must not crash the GUI
        logger.error("Failed to read blocker storage file %s: %s", path, e)
        return set()

    if not content:
        return set()

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(
            "Blocker storage file %s is corrupted (invalid JSON): %s", path, e
        )
        return set()

    if not isinstance(data, dict):
        logger.error(
            "Blocker storage file %s does not contain a JSON object", path
        )
        return set()

    channels = data.get(_CHANNELS_KEY, [])
    if not isinstance(channels, list):
        logger.error(
            "Blocker storage file %s: '%s' is not a list", path, _CHANNELS_KEY
        )
        return set()

    valid: Set[int] = set()
    for ch in channels:
        if isinstance(ch, bool) or not isinstance(ch, int):
            continue
        if RF_CHANNEL_MIN <= ch <= RF_CHANNEL_MAX:
            valid.add(ch)
        else:
            logger.warning(
                "Blocker storage file %s: channel %s out of range (0-125), ignored",
                path, ch,
            )

    if valid:
        logger.info("Loaded %d excluded channel(s) from %s", len(valid), path)
    return valid


def clear_storage_file() -> None:
    """Remove the blocker storage file if it exists.

    Used when the user clears all exclusions; safe if the file is missing.
    """
    path = _BLOCKER_STORAGE_FILE
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info("Removed blocker storage file %s", path)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to remove blocker storage file %s: %s", path, e)
