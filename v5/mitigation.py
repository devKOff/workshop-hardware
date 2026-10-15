"""Mitigation and alert subsystem for RF Spectrum Visualizer V5."""

import time
import threading
import logging
import uuid
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

from config import AnomalyConfig, ThresholdConfig, ChannelConfig
from scanner import ChannelObservation
from anomaly_detector import AnomalyDetector, Anomaly, AnomalyType, AnomalyState, Severity
from logging_config import get_logger

logger = get_logger("rf_visualizer.mitigation")


class MitigationState(Enum):
    """Mitigation system states."""
    DISARMED = "DISARMED"
    ARMED = "ARMED"


@dataclass
class ChannelRecommendation:
    """Recommendation for a channel."""
    channel: int
    frequency_mhz: int
    activity_percentage: float
    confidence: float
    reason: str


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
        anomaly_config: AnomalyConfig,
        threshold_config: ThresholdConfig,
        channel_config: ChannelConfig,
        anomaly_detector: Optional[AnomalyDetector] = None,
        on_alert: Optional[Callable[[Anomaly], None]] = None,
        on_recommendation: Optional[Callable[[List[ChannelRecommendation]], None]] = None,
    ):
        self._anomaly_config = anomaly_config
        self._threshold_config = threshold_config
        self._channel_config = channel_config
        self._anomaly_detector = anomaly_detector
        self._on_alert = on_alert
        self._on_recommendation = on_recommendation
        
        self._lock = threading.RLock()
        self._state = MitigationState.DISARMED
        self._last_recommendations: List[ChannelRecommendation] = []
        self._recommendation_history: List[Dict] = []
        self._channel_peaks: Dict[int, float] = {}
        self._last_alert_time: Dict[int, float] = {}
    
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
            logger.info("Mitigation system DISARMED")
    
    def is_armed(self) -> bool:
        with self._lock:
            return self._state == MitigationState.ARMED
    
    def process_observation(
        self,
        obs: ChannelObservation,
        all_observations: Dict[int, ChannelObservation],
    ) -> List[Anomaly]:
        """Process a channel observation through anomaly detector."""
        with self._lock:
            if obs.activity_percentage is None:
                return []
            
            if obs.channel not in self._channel_peaks:
                self._channel_peaks[obs.channel] = 0.0
            self._channel_peaks[obs.channel] = max(
                self._channel_peaks[obs.channel],
                obs.activity_percentage
            )
            
            if self._state == MitigationState.DISARMED:
                return []
            
            anomalies = []
            if self._anomaly_detector:
                anomalies = self._anomaly_detector.process_observation(obs, all_observations)
            
            if anomalies:
                self._generate_recommendations(obs, all_observations, anomalies)
            
            return anomalies
    
    def _generate_recommendations(
        self,
        trigger_obs: ChannelObservation,
        all_observations: Dict[int, ChannelObservation],
        anomalies: List[Anomaly],
    ) -> None:
        """Generate safe channel recommendations based on anomalies."""
        recommendations = []
        
        for ch in self._channel_config.channel_range():
            if ch == trigger_obs.channel:
                continue
            
            obs = all_observations.get(ch)
            if not obs or not obs.data_sufficient or obs.activity_percentage is None:
                continue
            
            if obs.error:
                continue
            
            activity = obs.activity_percentage
            threshold = self._anomaly_config.persistent_threshold
            
            if activity < threshold - self._anomaly_config.hysteresis:
                confidence = 1.0 - (activity / (threshold - self._anomaly_config.hysteresis))
                confidence = max(0.5, min(1.0, confidence))
                
                recommendations.append(ChannelRecommendation(
                    channel=ch,
                    frequency_mhz=obs.frequency_mhz,
                    activity_percentage=activity,
                    confidence=confidence,
                    reason=f"Low activity ({activity:.1f}%) below threshold ({threshold}%)",
                ))
        
        recommendations.sort(key=lambda r: r.activity_percentage)
        self._last_recommendations = recommendations[:5]
        
        if self._last_recommendations:
            self._recommendation_history.append({
                "timestamp": time.time(),
                "trigger_channel": trigger_obs.channel,
                "trigger_activity": trigger_obs.activity_percentage,
                "recommendations": [
                    {"channel": r.channel, "activity": r.activity_percentage, "reason": r.reason}
                    for r in self._last_recommendations
                ],
            })
            
            if self._on_recommendation:
                self._on_recommendation(self._last_recommendations)
    
    def get_active_alerts(self) -> List[Anomaly]:
        """Get all currently active alerts."""
        with self._lock:
            if self._anomaly_detector:
                return self._anomaly_detector.get_active_anomalies()
            return []
    
    def get_alert_history(self, limit: int = 100) -> List[Anomaly]:
        """Get alert history."""
        with self._lock:
            if self._anomaly_detector:
                return self._anomaly_detector.get_anomaly_history(limit)
            return []
    
    def get_recommendations(self) -> List[ChannelRecommendation]:
        """Get last recommendations."""
        with self._lock:
            return list(self._last_recommendations)
    
    def get_channel_peaks(self) -> Dict[int, float]:
        """Get peak activity per channel."""
        with self._lock:
            return dict(self._channel_peaks)
    
    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        """Acknowledge an anomaly."""
        with self._lock:
            if self._anomaly_detector:
                return self._anomaly_detector.acknowledge_anomaly(anomaly_id)
            return False
    
    def clear_history(self) -> None:
        """Clear alert and recommendation history."""
        with self._lock:
            if self._anomaly_detector:
                self._anomaly_detector.clear_history()
            self._recommendation_history.clear()
            self._channel_peaks.clear()
            self._last_recommendations.clear()
            self._last_alert_time.clear()
    
    def export_events(self) -> List[Dict]:
        """Export events for logging."""
        with self._lock:
            events = []
            if self._anomaly_detector:
                for anomaly in self._anomaly_detector.get_anomaly_history(500):
                    events.append({
                        "event_id": anomaly.anomaly_id,
                        "timestamp": anomaly.detection_time,
                        "event_type": anomaly.anomaly_type.value,
                        "channel": anomaly.channel,
                        "frequency_mhz": anomaly.frequency_mhz,
                        "activity_percentage": anomaly.current_activity,
                        "threshold": self._anomaly_config.persistent_threshold,
                        "classification": anomaly.anomaly_type.value,
                        "recommended_response": anomaly.detection_reason,
                        "action_status": anomaly.state.value,
                        "backend": "sim",
                        "sample_count": anomaly.supporting_observations,
                        "rpd_positive_count": 0,
                        "measurement_window": 1.0,
                        "error_details": None,
                    })
            return events
    
    def get_channel_status(self, channel: int, obs: Optional[ChannelObservation]) -> str:
        """Get detailed channel status string."""
        with self._lock:
            if obs is None or obs.activity_percentage is None:
                return "UNKNOWN"
            
            if not obs.data_sufficient:
                return "INSUFFICIENT DATA"
            
            if obs.status == "SENSOR_ERROR":
                return "SENSOR ERROR"
            
            if self._anomaly_detector:
                channel_anomalies = self._anomaly_detector.get_channel_anomalies(channel)
                active = [a for a in channel_anomalies if a.state in (AnomalyState.NEW, AnomalyState.ONGOING)]
                if active:
                    return f"ANOMALY: {', '.join(a.anomaly_type.value for a in active)}"
            
            return obs.status