"""Channel classification module for RF Spectrum Visualizer V5."""

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

from config import ThresholdConfig, ChannelConfig

logger = logging.getLogger("rf_visualizer.classifier")


class ActivityCategory(Enum):
    """Activity classification categories."""
    CLEAR = "CLEAR"
    MODERATE = "MODERATE"
    BUSY = "BUSY"
    HEAVY_LOAD = "HEAVY LOAD"
    INSUFFICIENT_DATA = "INSUFFICIENT DATA"
    SENSOR_ERROR = "SENSOR ERROR"


@dataclass
class ClassificationResult:
    """Result of channel classification."""
    category: ActivityCategory
    activity_percentage: Optional[float]
    thresholds_used: Dict[str, int]
    data_sufficient: bool
    error: Optional[str] = None


class ChannelClassifier:
    """Classifies channel activity based on energy detection measurements."""
    
    def __init__(self, thresholds: ThresholdConfig, channel_config: ChannelConfig):
        self._thresholds = thresholds
        self._channel_config = channel_config
    
    @property
    def thresholds(self) -> ThresholdConfig:
        return self._thresholds
    
    def update_thresholds(self, thresholds: ThresholdConfig) -> None:
        """Update classification thresholds."""
        self._thresholds = thresholds
    
    def classify(
        self,
        activity_percentage: Optional[float],
        data_sufficient: bool = True,
        error: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify channel activity based on energy detection percentage.
        
        Args:
            activity_percentage: Estimated activity percentage (0-100), None if insufficient data
            data_sufficient: Whether enough valid samples were collected
            error: Any error that occurred during measurement
        
        Returns:
            ClassificationResult with category and metadata
        """
        if error:
            return ClassificationResult(
                category=ActivityCategory.SENSOR_ERROR,
                activity_percentage=activity_percentage,
                thresholds_used=self._thresholds.get_thresholds_dict(),
                data_sufficient=False,
                error=error,
            )
        
        if not data_sufficient or activity_percentage is None:
            return ClassificationResult(
                category=ActivityCategory.INSUFFICIENT_DATA,
                activity_percentage=activity_percentage,
                thresholds_used=self._thresholds.get_thresholds_dict(),
                data_sufficient=False,
                error="Insufficient valid samples for classification",
            )
        
        category_str = self._thresholds.classify(activity_percentage)
        category = ActivityCategory(category_str)
        
        return ClassificationResult(
            category=category,
            activity_percentage=activity_percentage,
            thresholds_used=self._thresholds.get_thresholds_dict(),
            data_sufficient=True,
            error=None,
        )
    
    def classify_multiple(
        self,
        observations: Dict[int, Dict[str, Any]],
    ) -> Dict[int, ClassificationResult]:
        """Classify multiple channels at once."""
        results = {}
        for channel, obs in observations.items():
            activity = obs.get("activity_percentage")
            data_sufficient = obs.get("data_sufficient", False)
            error = obs.get("error")
            results[channel] = self.classify(activity, data_sufficient, error)
        return results
    
    def get_threshold_boundaries(self) -> Dict[str, float]:
        """Get threshold boundaries for reference."""
        return {
            "clear_max": float(self._thresholds.clear_max),
            "moderate_max": float(self._thresholds.moderate_max),
            "busy_max": float(self._thresholds.busy_max),
            "heavy_min": float(self._thresholds.heavy_min),
        }
    
    def validate_thresholds(self) -> List[str]:
        """Validate threshold configuration, return list of warnings."""
        warnings = []
        
        if self._thresholds.clear_max < 5:
            warnings.append("CLEAR threshold very low (<5%), may cause false MODERATE classifications")
        if self._thresholds.moderate_max > 70:
            warnings.append("MODERATE threshold very high (>70%), may mask BUSY channels")
        if self._thresholds.busy_max < 50:
            warnings.append("BUSY threshold low (<50%), may cause false HEAVY LOAD classifications")
        if self._thresholds.heavy_min > 90:
            warnings.append("HEAVY LOAD threshold very high (>90%), rarely triggered")
        
        return warnings


class RecommendationEngine:
    """Provides channel recommendations based on activity classifications."""
    
    def __init__(self, classifier: ChannelClassifier, channel_config: ChannelConfig):
        self._classifier = classifier
        self._channel_config = channel_config
    
    def get_quiet_channels(
        self,
        observations: Dict[int, Dict[str, Any]],
        max_results: int = 5,
        max_activity: float = 25.0,
    ) -> List[int]:
        """Get channels with lowest observed activity."""
        candidates = []
        
        for ch in self._channel_config.channel_range():
            obs = observations.get(ch)
            if not obs:
                continue
            
            activity = obs.get("activity_percentage")
            data_sufficient = obs.get("data_sufficient", False)
            error = obs.get("error")
            
            if error or not data_sufficient or activity is None:
                continue
            
            if activity <= max_activity:
                candidates.append((ch, activity))
        
        candidates.sort(key=lambda x: x[1])
        return [ch for ch, _ in candidates[:max_results]]
    
    def get_busy_channels(
        self,
        observations: Dict[int, Dict[str, Any]],
        min_activity: float = 75.0,
    ) -> List[int]:
        """Get channels with high observed activity."""
        candidates = []
        
        for ch in self._channel_config.channel_range():
            obs = observations.get(ch)
            if not obs:
                continue
            
            activity = obs.get("activity_percentage")
            data_sufficient = obs.get("data_sufficient", False)
            error = obs.get("error")
            
            if error or not data_sufficient or activity is None:
                continue
            
            if activity >= min_activity:
                candidates.append((ch, activity))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [ch for ch, _ in candidates]
    
    def get_channel_explanation(
        self,
        channel: int,
        observations: Dict[int, Dict[str, Any]],
    ) -> str:
        """Get human-readable explanation for a channel's classification."""
        obs = observations.get(channel)
        if not obs:
            return f"Channel {channel}: No observation data available."
        
        activity = obs.get("activity_percentage")
        status = obs.get("status", "UNKNOWN")
        data_sufficient = obs.get("data_sufficient", False)
        error = obs.get("error")
        freq = self._channel_config.channel_to_frequency(channel)
        
        if error:
            return f"Channel {channel} ({freq} MHz): Sensor error - {error}"
        
        if not data_sufficient:
            valid = obs.get("valid_samples", 0)
            required = obs.get("min_valid_samples", 10)
            return (
                f"Channel {channel} ({freq} MHz): Insufficient data - "
                f"{valid}/{required} valid samples. Cannot reliably classify."
            )
        
        if activity is None:
            return f"Channel {channel} ({freq} MHz): No activity data available."
        
        thresholds = self._classifier.thresholds
        
        if activity <= thresholds.clear_max:
            return (
                f"Channel {channel} ({freq} MHz): CLEAR ({activity:.1f}% activity). "
                f"Well below threshold of {thresholds.clear_max}%. "
                f"Good candidate for communication."
            )
        elif activity <= thresholds.moderate_max:
            return (
                f"Channel {channel} ({freq} MHz): MODERATE ({activity:.1f}% activity). "
                f"Between {thresholds.clear_max}% and {thresholds.moderate_max}% thresholds. "
                f"Some RF energy detected but likely manageable."
            )
        elif activity <= thresholds.busy_max:
            return (
                f"Channel {channel} ({freq} MHz): BUSY ({activity:.1f}% activity). "
                f"Between {thresholds.moderate_max}% and {thresholds.busy_max}% thresholds. "
                f"Significant RF energy - may impact communication reliability."
            )
        else:
            return (
                f"Channel {channel} ({freq} MHz): HEAVY LOAD ({activity:.1f}% activity). "
                f"Exceeds {thresholds.heavy_min}% threshold. "
                f"Strong persistent RF energy detected. "
                f"Investigation recommended - possible interference or heavy Wi-Fi traffic."
            )