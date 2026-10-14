"""Mitigation and alert subsystem for RF Spectrum Visualizer."""

import time
import threading
import logging
import uuid
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

from config import MitigationConfig, ThresholdConfig, ChannelConfig
from scanner import ChannelObservation, ChannelStatus
from logging_config import log_countermeasure_event, get_logger

logger = get_logger("rf_visualizer.mitigation")


class MitigationState(Enum):
    """Mitigation system states."""
    DISARMED = "DISARMED"
    ARMED = "ARMED"


@dataclass
class ChannelAlert:
    """Alert for a specific channel."""
    channel: int
    frequency_mhz: int
    activity_percentage: float
    threshold: float
    classification: str
    persistence_start: float
    consecutive_windows: int
    last_alert_time: float = 0.0
    alert_count: int = 0
    recommended_channels: List[int] = field(default_factory=list)


@dataclass
class MitigationEvent:
    """Mitigation event record."""
    event_id: str
    timestamp: float
    event_type: str
    channel: int
    frequency_mhz: int
    activity_percentage: float
    threshold: float
    classification: str
    recommended_response: str
    action_status: str
    backend: str
    sample_count: int
    rpd_positive_count: int
    measurement_window: float
    error_details: Optional[str] = None


class MitigationEngine:
    """Passive detection, alerting, and safe recommendation engine."""
    
    def __init__(
        self,
        mitigation_config: MitigationConfig,
        threshold_config: ThresholdConfig,
        channel_config: ChannelConfig,
        on_alert: Optional[Callable[[ChannelAlert], None]] = None,
        on_recommendation: Optional[Callable[[List[int]], None]] = None,
    ):
        self._mitigation_config = mitigation_config
        self._threshold_config = threshold_config
        self._channel_config = channel_config
        self._on_alert = on_alert
        self._on_recommendation = on_recommendation
        
        self._lock = threading.RLock()
        self._state = MitigationState.DISARMED
        self._channel_alerts: Dict[int, ChannelAlert] = {}
        self._alert_history: List[MitigationEvent] = []
        self._recommendation_history: List[Dict] = []
        self._channel_peaks: Dict[int, float] = {}
        self._last_recommendations: List[int] = []
    
    @property
    def state(self) -> MitigationState:
        with self._lock:
            return self._state
    
    def arm(self) -> None:
        """Arm the mitigation system (enable alerts and recommendations)."""
        with self._lock:
            self._state = MitigationState.ARMED
            logger.info("Mitigation system ARMED")
    
    def disarm(self) -> None:
        """Disarm the mitigation system (passive observation only)."""
        with self._lock:
            self._state = MitigationState.DISARMED
            self._channel_alerts.clear()
            logger.info("Mitigation system DISARMED")
    
    def is_armed(self) -> bool:
        with self._lock:
            return self._state == MitigationState.ARMED
    
    def process_observation(
        self,
        obs: ChannelObservation,
        all_observations: Dict[int, ChannelObservation],
    ) -> Optional[ChannelAlert]:
        """Process a channel observation and check for alerts."""
        with self._lock:
            if obs.activity_percentage is None:
                return None
            
            if obs.channel not in self._channel_peaks:
                self._channel_peaks[obs.channel] = 0.0
            self._channel_peaks[obs.channel] = max(
                self._channel_peaks[obs.channel],
                obs.activity_percentage
            )
            
            if self._state == MitigationState.DISARMED:
                return None
            
            return self._check_persistent_activity(obs, all_observations)
    
    def _check_persistent_activity(
        self,
        obs: ChannelObservation,
        all_observations: Dict[int, ChannelObservation],
    ) -> Optional[ChannelAlert]:
        """Check for persistent high activity and generate alerts."""
        threshold = self._mitigation_config.persistent_threshold
        now = time.time()
        
        if obs.activity_percentage >= threshold:
            if obs.channel not in self._channel_alerts:
                self._channel_alerts[obs.channel] = ChannelAlert(
                    channel=obs.channel,
                    frequency_mhz=obs.frequency_mhz,
                    activity_percentage=obs.activity_percentage,
                    threshold=threshold,
                    classification=obs.status,
                    persistence_start=now,
                    consecutive_windows=1,
                )
            else:
                alert = self._channel_alerts[obs.channel]
                alert.activity_percentage = obs.activity_percentage
                alert.classification = obs.status
                alert.consecutive_windows += 1
                
                if alert.consecutive_windows >= self._mitigation_config.consecutive_windows:
                    persistence_duration = now - alert.persistence_start
                    if persistence_duration >= self._mitigation_config.persistence_duration:
                        if now - alert.last_alert_time >= self._mitigation_config.alert_cooldown:
                            return self._trigger_alert(alert, obs, all_observations)
        else:
            if obs.channel in self._channel_alerts:
                alert = self._channel_alerts[obs.channel]
                if obs.activity_percentage < threshold - self._mitigation_config.hysteresis:
                    del self._channel_alerts[obs.channel]
        
        return None
    
    def _trigger_alert(
        self,
        alert: ChannelAlert,
        obs: ChannelObservation,
        all_observations: Dict[int, ChannelObservation],
    ) -> ChannelAlert:
        """Trigger an alert and generate recommendations."""
        recommendations = self._get_safe_recommendations(obs.channel, all_observations)
        alert.recommended_channels = recommendations
        alert.last_alert_time = time.time()
        alert.alert_count += 1
        
        event = MitigationEvent(
            event_id=str(uuid.uuid4())[:8],
            timestamp=alert.last_alert_time,
            event_type="PERSISTENT_HIGH_ACTIVITY",
            channel=alert.channel,
            frequency_mhz=alert.frequency_mhz,
            activity_percentage=alert.activity_percentage,
            threshold=alert.threshold,
            classification=alert.classification,
            recommended_response=f"Consider channels: {recommendations}" if recommendations else "No clear alternative",
            action_status="ALERT_GENERATED",
            backend=obs.backend,
            sample_count=obs.valid_samples,
            rpd_positive_count=obs.rpd_positive,
            measurement_window=obs.measurement_window,
        )
        
        self._alert_history.append(event)
        self._last_recommendations = recommendations
        
        log_countermeasure_event(
            logger=logger,
            event_id=event.event_id,
            event_type=event.event_type,
            backend=event.backend,
            channel=event.channel,
            frequency_mhz=event.frequency_mhz,
            activity_percentage=event.activity_percentage,
            sample_count=event.sample_count,
            rpd_positive_count=event.rpd_positive_count,
            measurement_window=event.measurement_window,
            threshold=event.threshold,
            classification=event.classification,
            recommended_response=event.recommended_response,
            action_status=event.action_status,
        )
        
        if self._on_alert:
            self._on_alert(alert)
        
        if self._on_recommendation and recommendations:
            self._on_recommendation(recommendations)
        
        return alert
    
    def _get_safe_recommendations(
        self,
        current_channel: int,
        all_observations: Dict[int, ChannelObservation],
    ) -> List[int]:
        """Get channels with lower observed activity."""
        candidates = []
        
        for ch in self._channel_config.channel_range():
            if ch == current_channel:
                continue
            
            obs = all_observations.get(ch)
            if obs and obs.data_sufficient and obs.activity_percentage is not None:
                if obs.activity_percentage < self._mitigation_config.persistent_threshold - self._mitigation_config.hysteresis:
                    candidates.append((ch, obs.activity_percentage))
        
        candidates.sort(key=lambda x: x[1])
        return [ch for ch, _ in candidates[:5]]
    
    def get_active_alerts(self) -> List[ChannelAlert]:
        """Get all currently active alerts."""
        with self._lock:
            return [deepcopy(a) for a in self._channel_alerts.values()]
    
    def get_alert_history(self, limit: int = 100) -> List[MitigationEvent]:
        """Get alert history."""
        with self._lock:
            return deepcopy(self._alert_history[-limit:])
    
    def get_recommendations(self) -> List[int]:
        """Get last recommendations."""
        with self._lock:
            return list(self._last_recommendations)
    
    def get_channel_peaks(self) -> Dict[int, float]:
        """Get peak activity per channel."""
        with self._lock:
            return dict(self._channel_peaks)
    
    def get_channel_status(self, channel: int, obs: Optional[ChannelObservation]) -> ChannelStatus:
        """Get detailed channel status."""
        with self._lock:
            if obs is None or obs.activity_percentage is None:
                return ChannelStatus.INSUFFICIENT_DATA
            
            if not obs.data_sufficient:
                return ChannelStatus.INSUFFICIENT_DATA
            
            if obs.status == "SENSOR_ERROR":
                return ChannelStatus.SENSOR_ERROR
            
            if channel in self._channel_alerts:
                return ChannelStatus.PERSISTENT_HIGH_ACTIVITY
            
            if obs.activity_percentage >= self._mitigation_config.persistent_threshold:
                return ChannelStatus.ELEVATED_ACTIVITY
            
            return ChannelStatus.NORMAL
    
    def clear_history(self) -> None:
        """Clear alert and recommendation history."""
        with self._lock:
            self._alert_history.clear()
            self._recommendation_history.clear()
            self._channel_peaks.clear()
            self._last_recommendations.clear()
    
    def export_events(self) -> List[Dict]:
        """Export events for logging."""
        with self._lock:
            return [
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "channel": e.channel,
                    "frequency_mhz": e.frequency_mhz,
                    "activity_percentage": e.activity_percentage,
                    "threshold": e.threshold,
                    "classification": e.classification,
                    "recommended_response": e.recommended_response,
                    "action_status": e.action_status,
                    "backend": e.backend,
                    "sample_count": e.sample_count,
                    "rpd_positive_count": e.rpd_positive_count,
                    "measurement_window": e.measurement_window,
                    "error_details": e.error_details,
                }
                for e in self._alert_history
            ]