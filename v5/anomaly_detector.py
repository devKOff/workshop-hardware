"""Anomaly detection engine for RF Spectrum Visualizer V5."""

import time
import threading
import logging
import uuid
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
from collections import deque

from config import AnomalyConfig, ThresholdConfig, ChannelConfig
from scanner import ChannelObservation
from logging_config import log_anomaly_event, get_logger

logger = get_logger("rf_visualizer.anomaly")


class AnomalyType(Enum):
    """Types of detectable anomalies."""
    PERSISTENT_HIGH_ACTIVITY = "PERSISTENT_HIGH_ACTIVITY"
    SUDDEN_SPIKE = "SUDDEN_SPIKE"
    UNUSUAL_INCREASE = "UNUSUAL_INCREASE"
    UNUSUAL_DECREASE = "UNUSUAL_DECREASE"
    INTERMITTENT_BURSTS = "INTERMITTENT_BURSTS"
    REPEATED_BURSTS = "REPEATED_BURSTS"
    CONSECUTIVE_CHANGE = "CONSECUTIVE_CHANGE"
    HOPPING_PATTERN = "HOPPING_PATTERN"
    INSUFFICIENT_BASELINE = "INSUFFICIENT_BASELINE"
    SENSOR_ERROR = "SENSOR_ERROR"
    NO_ANOMALY = "NO_ANOMALY"


class AnomalyState(Enum):
    """Anomaly lifecycle states."""
    NEW = "NEW"
    ONGOING = "ONGOING"
    RESOLVED = "RESOLVED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class Severity(Enum):
    """Anomaly severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    anomaly_id: str
    anomaly_type: AnomalyType
    channel: int
    frequency_mhz: int
    detection_time: float
    current_activity: float
    baseline_activity: Optional[float]
    difference_from_baseline: Optional[float]
    supporting_observations: int
    severity: Severity
    detection_reason: str
    confidence: float
    state: AnomalyState = AnomalyState.NEW
    last_seen: float = field(default_factory=time.time)
    acknowledged: bool = False
    resolved_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type.value,
            "channel": self.channel,
            "frequency_mhz": self.frequency_mhz,
            "detection_time": self.detection_time,
            "detection_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.detection_time)),
            "current_activity": self.current_activity,
            "baseline_activity": self.baseline_activity,
            "difference_from_baseline": self.difference_from_baseline,
            "supporting_observations": self.supporting_observations,
            "severity": self.severity.value,
            "detection_reason": self.detection_reason,
            "confidence": self.confidence,
            "state": self.state.value,
            "last_seen": self.last_seen,
            "last_seen_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_seen)),
            "acknowledged": self.acknowledged,
            "resolved_time": self.resolved_time,
            "resolved_time_iso": (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.resolved_time))
                if self.resolved_time else None
            ),
        }
    
    def update_seen(self) -> None:
        self.last_seen = time.time()


@dataclass
class BaselineData:
    """Rolling baseline for a channel."""
    channel: int
    observations: deque = field(default_factory=lambda: deque(maxlen=100))
    mean_activity: float = 0.0
    std_activity: float = 0.0
    sample_count: int = 0
    last_updated: float = 0.0
    is_established: bool = False
    
    def add_observation(self, activity: float) -> None:
        self.observations.append(activity)
        self._recalculate()
        self.last_updated = time.time()
    
    def _recalculate(self) -> None:
        if len(self.observations) < 2:
            self.mean_activity = self.observations[0] if self.observations else 0.0
            self.std_activity = 0.0
            self.sample_count = len(self.observations)
            self.is_established = self.sample_count >= 10
            return
        
        self.sample_count = len(self.observations)
        self.mean_activity = sum(self.observations) / self.sample_count
        variance = sum((x - self.mean_activity) ** 2 for x in self.observations) / self.sample_count
        self.std_activity = variance ** 0.5
        self.is_established = self.sample_count >= 10
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "mean": self.mean_activity,
            "std": self.std_activity,
            "count": self.sample_count,
            "established": self.is_established,
            "last_updated": self.last_updated,
        }


class AnomalyDetector:
    """Detects anomalies in RF channel activity patterns."""
    
    def __init__(
        self,
        anomaly_config: AnomalyConfig,
        threshold_config: ThresholdConfig,
        channel_config: ChannelConfig,
        on_anomaly: Optional[Callable[[Anomaly], None]] = None,
    ):
        self._config = anomaly_config
        self._thresholds = threshold_config
        self._channel_config = channel_config
        self._on_anomaly = on_anomaly
        
        self._lock = threading.RLock()
        self._baselines: Dict[int, BaselineData] = {}
        self._active_anomalies: Dict[str, Anomaly] = {}
        self._anomaly_history: List[Anomaly] = []
        self._channel_last_activity: Dict[int, float] = {}
        self._channel_burst_state: Dict[int, Dict] = {}
        self._scan_count = 0
    
    def process_observation(
        self,
        obs: ChannelObservation,
        all_observations: Dict[int, ChannelObservation],
    ) -> List[Anomaly]:
        """Process a channel observation and detect anomalies."""
        with self._lock:
            self._scan_count += 1
            anomalies = []
            
            if obs.activity_percentage is None:
                return self._handle_insufficient_data(obs)
            
            self._update_baseline(obs)
            
            new_anomalies = []
            new_anomalies.extend(self._check_persistent_high(obs))
            new_anomalies.extend(self._check_sudden_spike(obs))
            new_anomalies.extend(self._check_unusual_change(obs))
            new_anomalies.extend(self._check_intermittent_bursts(obs))
            new_anomalies.extend(self._check_hopping_pattern(obs, all_observations))
            
            self._update_anomaly_states(obs, all_observations)
            
            for anomaly in new_anomalies:
                self._active_anomalies[anomaly.anomaly_id] = anomaly
                self._anomaly_history.append(anomaly)
                self._log_anomaly(anomaly)
                if self._on_anomaly:
                    self._on_anomaly(anomaly)
            
            return new_anomalies
    
    def _handle_insufficient_data(self, obs: ChannelObservation) -> List[Anomaly]:
        if obs.error:
            return self._create_sensor_error_anomaly(obs)
        return []
    
    def _create_sensor_error_anomaly(self, obs: ChannelObservation) -> List[Anomaly]:
        anomaly = Anomaly(
            anomaly_id=str(uuid.uuid4())[:8],
            anomaly_type=AnomalyType.SENSOR_ERROR,
            channel=obs.channel,
            frequency_mhz=obs.frequency_mhz,
            detection_time=time.time(),
            current_activity=0.0,
            baseline_activity=None,
            difference_from_baseline=None,
            supporting_observations=0,
            severity=Severity.MEDIUM,
            detection_reason=f"Sensor error: {obs.error}",
            confidence=1.0,
        )
        return [anomaly]
    
    def _update_baseline(self, obs: ChannelObservation) -> None:
        if obs.channel not in self._baselines:
            self._baselines[obs.channel] = BaselineData(channel=obs.channel)
        
        if obs.data_sufficient and obs.activity_percentage is not None:
            self._baselines[obs.channel].add_observation(obs.activity_percentage)
    
    def _get_baseline(self, channel: int) -> Optional[BaselineData]:
        return self._baselines.get(channel)
    
    def _check_persistent_high(self, obs: ChannelObservation) -> List[Anomaly]:
        if not obs.data_sufficient or obs.activity_percentage is None:
            return []
        
        baseline = self._get_baseline(obs.channel)
        if not baseline or not baseline.is_established:
            return []
        
        threshold = self._config.persistent_threshold
        if obs.activity_percentage >= threshold:
            if obs.activity_percentage - baseline.mean_activity >= self._config.hysteresis:
                return [self._create_anomaly(
                    obs=obs,
                    anomaly_type=AnomalyType.PERSISTENT_HIGH_ACTIVITY,
                    baseline=baseline,
                    severity=Severity.HIGH if obs.activity_percentage >= 90 else Severity.MEDIUM,
                    reason=f"Activity {obs.activity_percentage:.1f}% exceeds persistent threshold {threshold}% "
                           f"(baseline: {baseline.mean_activity:.1f}%)",
                    confidence=min(1.0, (obs.activity_percentage - threshold) / 25.0),
                )]
        
        return []
    
    def _check_sudden_spike(self, obs: ChannelObservation) -> List[Anomaly]:
        if not obs.data_sufficient or obs.activity_percentage is None:
            return []
        
        last_activity = self._channel_last_activity.get(obs.channel)
        if last_activity is None:
            self._channel_last_activity[obs.channel] = obs.activity_percentage
            return []
        
        change = obs.activity_percentage - last_activity
        self._channel_last_activity[obs.channel] = obs.activity_percentage
        
        if change >= self._config.spike_threshold:
            baseline = self._get_baseline(obs.channel)
            baseline_activity = baseline.mean_activity if baseline else None
            
            return [self._create_anomaly(
                obs=obs,
                anomaly_type=AnomalyType.SUDDEN_SPIKE,
                baseline=baseline,
                severity=Severity.HIGH if change >= 50 else Severity.MEDIUM,
                reason=f"Sudden increase of {change:.1f}% from previous scan "
                       f"({last_activity:.1f}% -> {obs.activity_percentage:.1f}%)",
                confidence=min(1.0, change / 50.0),
            )]
        
        return []
    
    def _check_unusual_change(self, obs: ChannelObservation) -> List[Anomaly]:
        if not obs.data_sufficient or obs.activity_percentage is None:
            return []
        
        baseline = self._get_baseline(obs.channel)
        if not baseline or not baseline.is_established:
            return []
        
        change = obs.activity_percentage - baseline.mean_activity
        
        if abs(change) >= self._config.change_threshold:
            if change > 0:
                anomaly_type = AnomalyType.UNUSUAL_INCREASE
            else:
                anomaly_type = AnomalyType.UNUSUAL_DECREASE
            
            return [self._create_anomaly(
                obs=obs,
                anomaly_type=anomaly_type,
                baseline=baseline,
                severity=Severity.MEDIUM,
                reason=f"Activity {obs.activity_percentage:.1f}% deviates from baseline "
                       f"{baseline.mean_activity:.1f}% by {abs(change):.1f}% "
                       f"(threshold: {self._config.change_threshold}%)",
                confidence=min(1.0, abs(change) / 50.0),
            )]
        
        return []
    
    def _check_intermittent_bursts(self, obs: ChannelObservation) -> List[Anomaly]:
        if not obs.data_sufficient or obs.activity_percentage is None:
            return []
        
        if obs.channel not in self._channel_burst_state:
            self._channel_burst_state[obs.channel] = {
                "burst_count": 0,
                "last_burst_scan": -1,
                "in_burst": False,
            }
        
        state = self._channel_burst_state[obs.channel]
        threshold = self._config.burst_threshold
        
        is_burst = obs.activity_percentage >= threshold
        
        if is_burst:
            if not state["in_burst"]:
                state["in_burst"] = True
                state["burst_count"] += 1
                state["last_burst_scan"] = self._scan_count
        else:
            if state["in_burst"]:
                state["in_burst"] = False
            
            if (state["burst_count"] >= self._config.burst_min_windows and
                self._scan_count - state["last_burst_scan"] <= self._config.burst_max_gap):
                
                baseline = self._get_baseline(obs.channel)
                anomaly = self._create_anomaly(
                    obs=obs,
                    anomaly_type=AnomalyType.INTERMITTENT_BURSTS,
                    baseline=baseline,
                    severity=Severity.MEDIUM,
                    reason=f"Detected {state['burst_count']} burst windows "
                           f"(threshold: {threshold}%)",
                    confidence=0.7,
                )
                state["burst_count"] = 0
                return [anomaly]
        
        return []
    
    def _check_hopping_pattern(self, obs: ChannelObservation, 
                                all_observations: Dict[int, ChannelObservation]) -> List[Anomaly]:
        if not obs.data_sufficient or obs.activity_percentage is None:
            return []
        
        if obs.activity_percentage < self._config.burst_threshold:
            return []
        
        active_channels = [
            ch for ch, o in all_observations.items()
            if o.data_sufficient and o.activity_percentage is not None
            and o.activity_percentage >= self._config.burst_threshold
        ]
        
        if len(active_channels) >= self._config.hopping_min_channels:
            recent_scans = min(self._config.hopping_max_interval, self._scan_count)
            
            return [self._create_anomaly(
                obs=obs,
                anomaly_type=AnomalyType.HOPPING_PATTERN,
                baseline=None,
                severity=Severity.LOW,
                reason=f"Hopping-like pattern: {len(active_channels)} channels "
                       f"simultaneously active above {self._config.burst_threshold}%: "
                       f"{active_channels}",
                confidence=0.6,
            )]
        
        return []
    
    def _create_anomaly(
        self,
        obs: ChannelObservation,
        anomaly_type: AnomalyType,
        baseline: Optional[BaselineData],
        severity: Severity,
        reason: str,
        confidence: float,
    ) -> Anomaly:
        baseline_activity = baseline.mean_activity if baseline else None
        diff = None
        if baseline_activity is not None and obs.activity_percentage is not None:
            diff = obs.activity_percentage - baseline_activity
        
        anomaly = Anomaly(
            anomaly_id=str(uuid.uuid4())[:8],
            anomaly_type=anomaly_type,
            channel=obs.channel,
            frequency_mhz=obs.frequency_mhz,
            detection_time=time.time(),
            current_activity=obs.activity_percentage or 0.0,
            baseline_activity=baseline_activity,
            difference_from_baseline=diff,
            supporting_observations=obs.valid_samples,
            severity=severity,
            detection_reason=reason,
            confidence=confidence,
        )
        return anomaly
    
    def _update_anomaly_states(
        self,
        obs: ChannelObservation,
        all_observations: Dict[int, ChannelObservation],
    ) -> None:
        to_remove = []
        
        for anomaly_id, anomaly in self._active_anomalies.items():
            if anomaly.channel != obs.channel:
                continue
            
            if anomaly.state in (AnomalyState.RESOLVED, AnomalyState.ACKNOWLEDGED):
                continue
            
            should_resolve = False
            
            if anomaly.anomaly_type == AnomalyType.PERSISTENT_HIGH_ACTIVITY:
                baseline = self._get_baseline(obs.channel)
                if baseline and baseline.is_established:
                    if obs.activity_percentage is not None:
                        if obs.activity_percentage < self._config.persistent_threshold - self._config.hysteresis:
                            should_resolve = True
            
            elif anomaly.anomaly_type == AnomalyType.SUDDEN_SPIKE:
                if obs.activity_percentage is not None:
                    if obs.activity_percentage < self._config.spike_threshold:
                        should_resolve = True
            
            elif anomaly.anomaly_type in (AnomalyType.UNUSUAL_INCREASE, AnomalyType.UNUSUAL_DECREASE):
                baseline = self._get_baseline(obs.channel)
                if baseline and baseline.is_established and obs.activity_percentage is not None:
                    if abs(obs.activity_percentage - baseline.mean_activity) < self._config.change_threshold - self._config.hysteresis:
                        should_resolve = True
            
            if should_resolve:
                anomaly.state = AnomalyState.RESOLVED
                anomaly.resolved_time = time.time()
                to_remove.append(anomaly_id)
            else:
                anomaly.state = AnomalyState.ONGOING
                anomaly.update_seen()
        
        for aid in to_remove:
            del self._active_anomalies[aid]
    
    def _log_anomaly(self, anomaly: Anomaly) -> None:
        log_anomaly_event(
            logger=logger,
            event_id=anomaly.anomaly_id,
            event_type=anomaly.anomaly_type.value,
            backend="sim",  # Will be updated by caller
            channel=anomaly.channel,
            frequency_mhz=anomaly.frequency_mhz,
            activity_percentage=anomaly.current_activity,
            baseline_activity=anomaly.baseline_activity,
            difference_from_baseline=anomaly.difference_from_baseline,
            sample_count=anomaly.supporting_observations,
            rpd_positive_count=0,
            measurement_window=1.0,
            threshold=self._config.persistent_threshold,
            classification=anomaly.anomaly_type.value,
            severity=anomaly.severity.value,
            detection_reason=anomaly.detection_reason,
            confidence=anomaly.confidence,
            state=anomaly.state.value,
        )
    
    def get_active_anomalies(self) -> List[Anomaly]:
        with self._lock:
            return [deepcopy(a) for a in self._active_anomalies.values()]
    
    def get_anomaly_history(self, limit: int = 100) -> List[Anomaly]:
        with self._lock:
            return [deepcopy(a) for a in self._anomaly_history[-limit:]]
    
    def get_channel_anomalies(self, channel: int) -> List[Anomaly]:
        with self._lock:
            return [
                deepcopy(a) for a in self._active_anomalies.values()
                if a.channel == channel
            ] + [
                deepcopy(a) for a in self._anomaly_history[-50:]
                if a.channel == channel
            ]
    
    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        with self._lock:
            if anomaly_id in self._active_anomalies:
                self._active_anomalies[anomaly_id].acknowledged = True
                self._active_anomalies[anomaly_id].state = AnomalyState.ACKNOWLEDGED
                return True
        return False
    
    def get_baseline_stats(self, channel: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            baseline = self._baselines.get(channel)
            return baseline.get_stats() if baseline else None
    
    def clear_history(self) -> None:
        with self._lock:
            self._baselines.clear()
            self._active_anomalies.clear()
            self._anomaly_history.clear()
            self._channel_last_activity.clear()
            self._channel_burst_state.clear()
            self._scan_count = 0
    
    def export_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in self._anomaly_history]