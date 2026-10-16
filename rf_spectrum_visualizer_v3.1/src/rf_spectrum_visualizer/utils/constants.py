"""Utility-specific constants (re-exported for convenience).

Re-exports the RF channel constants from the main constants module so that
utility modules can import from a single location.
"""

from ..constants import RF_CHANNEL_MAX, RF_CHANNEL_MIN, RF_BASE_FREQUENCY_MHZ  # noqa: F401

__all__ = ["RF_CHANNEL_MIN", "RF_CHANNEL_MAX", "RF_BASE_FREQUENCY_MHZ"]
