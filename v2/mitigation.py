"""Active signal mitigation with software interlock and audit logging."""
import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
from pathlib import Path

from config import MitigationConfig
from hardware_radio import RadioInterface
from scanner import SpectrumData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MitigationEvent:
    """Immutable record of a mitigation action."""
    timestamp: datetime
    channel: int
    frequency_mhz: float
    peak_intensity_db: float
    duration_ms: int
    mitigation_type: str
    triggered: bool
    reason: str = "threshold_exceeded"


class MitigationEngine:
    """Active signal mitigation with software interlock and audit logging."""
    
    def __init__(
        self,
        radio: RadioInterface,
        spectrum_data: SpectrumData,
        config: Optional[MitigationConfig] = None,
    ):
        self._radio = radio
        self._spectrum_data = spectrum_data
        self._config = config or MitigationConfig()
        
        # Thread safety
        self._lock = threading.RLock()
        self._audit_lock = threading.Lock()
        
        # State
        self._armed = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._last_mitigation_time = 0.0
        
        # Configuration (mutable at runtime)
        self._threshold_db = self._config.default_threshold_db
        self._target_channels = list(self._config.default_target_channels)
        self._mitigation_type = self._config.default_type
        self._event_callback: Optional[Callable[[MitigationEvent], None]] = None
        
        # Audit log
        self._audit_path = Path(self._config.audit_log_path)
    
    # Properties
    
    @property
    def armed(self) -> bool:
        with self._lock:
            return self._armed
    
    @property
    def threshold_db(self) -> float:
        with self._lock:
            return self._threshold_db
    
    @property
    def target_channels(self) -> List[int]:
        with self._lock:
            return list(self._target_channels)
    
    @property
    def mitigation_type(self) -> str:
        with self._lock:
            return self._mitigation_type
    
    @property
    def last_mitigation_ms_ago(self) -> int:
        with self._lock:
            if self._last_mitigation_time > 0:
                return int((time.monotonic() - self._last_mitigation_time) * 1000)
            return -1
    
    # Configuration setters
    
    def set_threshold(self, threshold_db: float):
        with self._lock:
            self._threshold_db = max(-100.0, min(0.0, threshold_db))
    
    def set_target_channels(self, channels: List[int]):
        with self._lock:
            self._target_channels = [c for c in channels if 0 <= c <= 125]
    
    def set_mitigation_type(self, mtype: str):
        with self._lock:
            if mtype in ("carrier", "noise"):
                self._mitigation_type = mtype
            else:
                raise ValueError(f"Invalid mitigation type: {mtype}")
    
    def set_event_callback(self, callback: Callable[[MitigationEvent], None]):
        with self._lock:
            self._event_callback = callback
    
    # Interlock control
    
    def arm(self) -> bool:
        """Enable mitigation (software interlock). Returns True if armed."""
        with self._lock:
            if self._armed:
                return True
            
            if not self._target_channels:
                logger.warning("Cannot arm: no target channels configured")
                return False
            
            self._armed = True
            logger.warning("MITIGATION ARMED - Active countermeasures enabled")
            return True
    
    def disarm(self):
        """Disable mitigation (software interlock)."""
        with self._lock:
            self._armed = False
            logger.info("Mitigation disarmed")
    
    # Monitoring
    
    def start_monitoring(self):
        """Start background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._running.set()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="MitigationMonitor"
        )
        self._monitor_thread.start()
        logger.info("Mitigation monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self._running.clear()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Mitigation monitoring stopped")
    
    def _monitor_loop(self):
        """Background loop checking threshold conditions."""
        while self._running.is_set():
            if not self._armed:
                time.sleep(0.1)
                continue
            
            current_time = time.monotonic()
            min_interval = self._config.min_interval_ms / 1000.0
            
            if current_time - self._last_mitigation_time < min_interval:
                time.sleep(0.05)
                continue
            
            # Check peak hold against threshold
            peak_hold = self._spectrum_data.get_peak_hold()
            
            with self._lock:
                targets = list(self._target_channels)
                threshold = self._threshold_db
                mtype = self._mitigation_type
            
            for channel in targets:
                if peak_hold[channel] >= threshold:
                    self._execute_mitigation(
                        channel, 
                        peak_hold[channel], 
                        mtype,
                        "threshold_exceeded"
                    )
                    self._last_mitigation_time = time.monotonic()
                    break
            
            time.sleep(0.05)
    
    def _execute_mitigation(
        self, 
        channel: int, 
        peak_db: float, 
        mtype: str,
        reason: str
    ):
        """Execute mitigation action on channel."""
        freq_mhz = 2400 + channel
        duration_ms = min(
            self._config.max_duration_ms,
            max(100, int((peak_db - (-50)) * 50))
        )
        
        logger.warning(f"MITIGATION TRIGGERED: Ch {channel} ({freq_mhz} MHz) "
                      f"Peak: {peak_db:.1f} dBm Type: {mtype} Duration: {duration_ms}ms")
        
        success = False
        try:
            if mtype == "carrier":
                success = self._radio.transmit_carrier(channel, duration_ms)
            elif mtype == "noise":
                packets = max(1, duration_ms // 10)
                success = self._radio.transmit_noise(channel, packets)
        except Exception as e:
            logger.error(f"Mitigation execution failed: {e}")
            success = False
        
        event = MitigationEvent(
            timestamp=datetime.now(),
            channel=channel,
            frequency_mhz=freq_mhz,
            peak_intensity_db=peak_db,
            duration_ms=duration_ms,
            mitigation_type=mtype,
            triggered=success,
            reason=reason
        )
        
        self._log_event(event)
        
        if self._event_callback:
            try:
                self._event_callback(event)
            except Exception as e:
                logger.error(f"Event callback failed: {e}")
    
    def _log_event(self, event: MitigationEvent):
        """Write mitigation event to audit log."""
        log_line = (
            f"{event.timestamp.isoformat()},"
            f"ch={event.channel},"
            f"freq={event.frequency_mhz:.1f}MHz,"
            f"peak={event.peak_intensity_db:.1f}dBm,"
            f"duration={event.duration_ms}ms,"
            f"type={event.mitigation_type},"
            f"triggered={event.triggered},"
            f"reason={event.reason}\n"
        )
        
        with self._audit_lock:
            try:
                self._audit_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._audit_path, "a") as f:
                    f.write(log_line)
            except Exception as e:
                logger.error(f"Audit log write failed: {e}")
    
    # Manual trigger
    
    def manual_trigger(self, channel: int, duration_ms: Optional[int] = None) -> bool:
        """Manually trigger mitigation on a channel (requires armed)."""
        with self._lock:
            if not self._armed:
                logger.warning("Cannot trigger: mitigation not armed")
                return False
            
            if not (0 <= channel <= 125):
                return False
            
            peak_hold = self._spectrum_data.get_peak_hold()
            peak_db = peak_hold[channel]
            
            if duration_ms is None:
                duration_ms = min(
                    self._config.max_duration_ms,
                    max(100, int((peak_db - (-50)) * 50))
                )
            
            self._execute_mitigation(channel, peak_db, self._mitigation_type, "manual")
            return True
    
    # Audit log access
    
    def get_recent_events(self, count: int = 50) -> List[MitigationEvent]:
        """Parse recent events from audit log."""
        events = []
        try:
            with open(self._audit_path, "r") as f:
                lines = f.readlines()[-count:]
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(",")
                    timestamp = datetime.fromisoformat(parts[0])
                    channel = int(parts[1].split("=")[1])
                    freq = float(parts[2].split("=")[1].replace("MHz", ""))
                    peak = float(parts[3].split("=")[1].replace("dBm", ""))
                    duration = int(parts[4].split("=")[1].replace("ms", ""))
                    mtype = parts[5].split("=")[1]
                    triggered = parts[6].split("=")[1].lower() == "true"
                    reason = parts[7].split("=")[1] if len(parts) > 7 else "unknown"
                    
                    events.append(MitigationEvent(
                        timestamp=timestamp,
                        channel=channel,
                        frequency_mhz=freq,
                        peak_intensity_db=peak,
                        duration_ms=duration,
                        mitigation_type=mtype,
                        triggered=triggered,
                        reason=reason
                    ))
                except Exception:
                    continue
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
        
        return events
    
    def get_status(self) -> Dict[str, Any]:
        """Get current mitigation status."""
        with self._lock:
            return {
                "armed": self._armed,
                "threshold_db": self._threshold_db,
                "target_channels": list(self._target_channels),
                "mitigation_type": self._mitigation_type,
                "min_interval_ms": self._config.min_interval_ms,
                "max_duration_ms": self._config.max_duration_ms,
                "last_mitigation_ms_ago": self.last_mitigation_ms_ago,
            }


def create_mitigation_engine(
    radio: RadioInterface,
    spectrum_data: SpectrumData,
    config: Optional[MitigationConfig] = None,
) -> MitigationEngine:
    """Factory to create mitigation engine."""
    return MitigationEngine(radio, spectrum_data, config)