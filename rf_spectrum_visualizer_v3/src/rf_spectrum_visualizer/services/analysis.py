"""Analysis service for RF Spectrum Visualizer V3.

Integrates V6's ChannelSelector as the channel selection and recommendation
engine. Provides channel eligibility assessment, rankings, statistics, and
blocklist-aware recommendations.

Key design decisions:
- Single ChannelSelector instance shared across all three GUI tools.
- Blocklist awareness: blocked channels are excluded from eligibility
  but remain visible in measurements.
- Peak tracking with persistent_threshold and hysteresis.
- Channel rankings sorted by activity (lowest activity first).
- Recommendations exclude blocked channels automatically via the blocklist.
- Channel assessments include eligibility reason (ELIGIBLE, BLOCKED,
  INSUFFICIENT_DATA, SENSOR_ERROR, HIGH_ACTIVITY, PERSISTENT_HIGH_ACTIVITY).

The analysis service uses V6's ChannelSelector which assesses each channel
based on its observation, activity percentage, blocklist status, and the
configured persistent threshold and hysteresis values.
"""

import logging
from typing import List, Optional, Dict, Any, Set

from ..models.channel import validate_channel, channel_to_frequency
from ..exceptions import InvalidChannelError

# Import V6's ChannelSelector directly (original source, not modified)
from v6.channel_selector import ChannelSelector, ChannelEligibility, EligibilityReason  # type: ignore
from v6.config import ChannelConfig, ThresholdConfig
from v6.blocklist_manager import BlocklistManager as V6BlocklistManager  # type: ignore
from v6.scanner import ChannelObservation

logger = logging.getLogger("rf_visualizer.services.analysis")


class AnalysisService:
    """Channel analysis and recommendation service.

    Wraps V6's ChannelSelector to provide channel eligibility assessment,
    rankings, and blocklist-aware recommendations across all three GUI tools.

    Responsibilities:
    - Assess channel eligibility based on observation data and blocklist status.
    - Rank all channels by activity (lowest activity first).
    - Get top N recommended channels (lowest activity, not blocked, sufficient data).
    - Provide explanations for recommendations.
    - Exclude blocked channels from eligible recommendations.
    - Keep blocked channels visible in measurements and status display.

    The ChannelSelector internally uses the blocklist to determine eligibility,
    so blocked channels are automatically excluded from recommendation results.
    However, blocked channels remain in the observed data and are visible in
    the Live Spectrum and Start Analysis tools.
    """

    def __init__(
        self,
        channel_config: ChannelConfig,
        threshold_config: ThresholdConfig,
        blocklist: V6BlocklistManager,
        persistent_threshold: float = 75.0,
        hysteresis: float = 5.0,
    ):
        """Initialize the analysis service.

        Args:
            channel_config: Channel configuration (start_channel, end_channel).
            threshold_config: Activity classification thresholds.
            blocklist: BlocklistManager instance for blockage checking.
            persistent_threshold: Threshold for persistent high activity detection.
            hysteresis: Hysteresis value for alert clearing.
        """
        self._channel_selector = ChannelSelector(
            channel_config,
            threshold_config,
            blocklist,
            persistent_threshold=persistent_threshold,
            hysteresis=hysteresis,
        )
        logger.info("Analysis service initialized with ChannelSelector")

    def assess_channel(
        self,
        channel: int,
        observation: Optional[Any] = None,
    ) -> Any:
        """Assess eligibility of a single channel.

        Args:
            channel: Channel number (0-125).
            observation: ChannelObservation or None. If None, channel is
                assessed as INSUFFICIENT_DATA.

        Returns:
            ChannelEligibility object with eligible status, reason,
            activity percentage, and blockage status.

        Raises:
            InvalidChannelError: If channel is out of range [0, 125].
        """
        validate_channel(channel)
        return self._channel_selector.assess_channel(channel, observation)

    def assess_all_channels(
        self,
        observations: Dict[int, Any],
    ) -> List[Any]:
        """Assess eligibility for all channels in the configured range.

        Args:
            observations: Dictionary mapping channel numbers to
                ChannelObservation objects.

        Returns:
            List of ChannelEligibility for all channels in the configured range.
        """
        return self._channel_selector.assess_all_channels(observations)

    def get_eligible_channels(
        self,
        observations: Dict[int, Any],
    ) -> List[Any]:
        """Get all eligible channels sorted by activity (lowest first).

        Args:
            observations: Dictionary mapping channel numbers to
                ChannelObservation objects.

        Returns:
            List of ChannelEligibility for eligible channels, sorted by
            activity_percentage ascending (lowest activity first).
        """
        return self._channel_selector.get_eligible_channels(observations)

    def recommend_channel(
        self,
        observations: Dict[int, Any],
        exclude_channels: Optional[Set[int]] = None,
    ) -> Optional[Any]:
        """Recommend the best channel (lowest activity, not blocked).

        Args:
            observations: Dictionary mapping channel numbers to
                ChannelObservation objects.
            exclude_channels: Additional channels to exclude beyond the
                blocklist.

        Returns:
            Best ChannelEligibility or None if no eligible channels.
        """
        return self._channel_selector.recommend_channel(observations, exclude_channels)

    def get_recommendations(
        self,
        observations: Dict[int, Any],
        count: int = 5,
        exclude_channels: Optional[Set[int]] = None,
    ) -> List[Any]:
        """Get top N recommended channels.

        Args:
            observations: Dictionary mapping channel numbers to
                ChannelObservation objects.
            count: Number of recommendations to return.
            exclude_channels: Additional channels to exclude beyond the
                blocklist.

        Returns:
            List of ChannelEligibility assessments, ordered by activity
            (lowest first), excluding blocked channels and any additional
            excluded channels.
        """
        return self._channel_selector.get_recommendations(observations, count, exclude_channels)

    def get_channel_ranking(
        self,
        observations: Dict[int, Any],
    ) -> List[tuple]:
        """Get all channels ranked by activity (lowest activity first).

        Args:
            observations: Dictionary mapping channel numbers to
                ChannelObservation objects.

        Returns:
            List of (channel, activity_percentage, status) tuples sorted
            by activity percentage ascending.
        """
        return self._channel_selector.get_channel_ranking(observations)

    def get_blocked_channels(self) -> List[int]:
        """Get list of currently blocked channels.

        Returns:
            Sorted list of blocked channel numbers.
        """
        return self._channel_selector.get_blocked_channels()

    def get_peak_activity(self, channel: int) -> float:
        """Get peak observed activity for a channel.

        Args:
            channel: Channel number (0-125).

        Returns:
            Peak activity percentage for the channel.
        """
        validate_channel(channel)
        return self._channel_selector.get_peak_activity(channel)

    def reset_peaks(self) -> None:
        """Reset peak activity tracking."""
        self._channel_selector.reset_peaks()

    def export_assessment(
        self,
        observations: Dict[int, Any],
    ) -> List[dict]:
        """Export full channel assessment as list of dicts.

        Args:
            observations: Dictionary mapping channel numbers to
                ChannelObservation objects.

        Returns:
            List of assessment dictionaries, one per channel in the
            configured range.
        """
        return self._channel_selector.export_assessment(observations)

    def get_status_summary(self) -> Dict[str, Any]:
        """Get status summary for UI display.

        Returns:
            Dictionary with analysis service configuration and blocked
            channel information.
        """
        return {
            "blocked_channels": self.get_blocked_channels(),
            "peak_tracking_enabled": True,
            "persistent_threshold": self._channel_selector.persistent_threshold,
            "hysteresis": self._channel_selector.hysteresis,
        }