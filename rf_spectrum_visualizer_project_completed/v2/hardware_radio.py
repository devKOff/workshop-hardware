"""Hardware radio interface for nRF24L01+ with robust SPI handling."""
import time
import threading
import logging
from typing import Optional, Tuple
from contextlib import contextmanager

from config import RadioConfig

logger = logging.getLogger(__name__)

# Try to import pyrf24, capture availability
try:
    from pyrf24 import (
        RF24, RF24_PA_LOW, RF24_PA_HIGH, RF24_PA_MAX,
        RF24_250KBPS, RF24_1MBPS, RF24_2MBPS
    )
    PYRF24_AVAILABLE = True
    _PA_LEVELS = {"LOW": RF24_PA_LOW, "HIGH": RF24_PA_HIGH, "MAX": RF24_PA_MAX}
    _DATA_RATES = {"250KBPS": RF24_250KBPS, "1MBPS": RF24_1MBPS, "2MBPS": RF24_2MBPS}
except ImportError:
    PYRF24_AVAILABLE = False
    RF24 = None
    _PA_LEVELS = {}
    _DATA_RATES = {}


class RadioError(Exception):
    """Base exception for radio operations."""
    pass


class RadioInitError(RadioError):
    """Radio initialization failed."""
    pass


class RadioOperationError(RadioError):
    """Radio operation failed."""
    pass


class HardwareRadio:
    """Thread-safe nRF24L01+ hardware interface."""
    
    def __init__(self, config: Optional[RadioConfig] = None):
        self._config = config or RadioConfig()
        self._radio: Optional[RF24] = None
        self._lock = threading.RLock()
        self._initialized = False
        self._init_error: Optional[str] = None
    
    @property
    def is_initialized(self) -> bool:
        with self._lock:
            return self._initialized
    
    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._init_error
    
    def initialize(self) -> bool:
        """Initialize the nRF24L01+ radio hardware."""
        if not PYRF24_AVAILABLE:
            self._init_error = "pyrf24 library not installed"
            logger.error(self._init_error)
            return False
        
        with self._lock:
            if self._initialized:
                return True
            
            try:
                self._radio = RF24(
                    self._config.ce_pin,
                    self._config.csn_pin,
                    self._config.spi_speed_hz,
                    self._config.spi_device
                )
                
                if not self._radio.begin():
                    raise RadioInitError("radio.begin() returned False - check wiring")
                
                # Configure radio
                pa_level = _PA_LEVELS.get(self._config.pa_level, RF24_PA_LOW)
                data_rate = _DATA_RATES.get(self._config.data_rate, RF24_2MBPS)
                
                self._radio.setPALevel(pa_level)
                self._radio.setDataRate(data_rate)
                self._radio.setAutoAck(False)
                self._radio.setRetries(0, 0)
                self._radio.setChannel(self._config.channel_min)
                self._radio.powerUp()
                self._radio.flush_rx()
                self._radio.flush_tx()
                
                self._initialized = True
                self._init_error = None
                logger.info(f"nRF24L01+ initialized on {self._config.spi_device} "
                           f"(CE={self._config.ce_pin}, CSN={self._config.csn_pin})")
                return True
                
            except Exception as e:
                self._init_error = str(e)
                logger.error(f"Hardware initialization failed: {e}")
                self._radio = None
                self._initialized = False
                return False
    
    def _require_initialized(self) -> RF24:
        """Get radio instance or raise if not initialized."""
        with self._lock:
            if not self._initialized or self._radio is None:
                raise RadioOperationError("Radio not initialized")
            return self._radio
    
    def set_channel(self, channel: int) -> bool:
        """Set radio to specific channel with settling delay."""
        if not (self._config.channel_min <= channel <= self._config.channel_max):
            raise ValueError(f"Channel {channel} out of range "
                           f"[{self._config.channel_min}-{self._config.channel_max}]")
        
        radio = self._require_initialized()
        with self._lock:
            try:
                radio.setChannel(channel)
                if self._config.settling_time_us > 0:
                    time.sleep(self._config.settling_time_us / 1_000_000.0)
                return True
            except Exception as e:
                logger.error(f"Failed to set channel {channel}: {e}")
                raise RadioOperationError(f"Channel set failed: {e}") from e
    
    def test_carrier(self, channel: int) -> bool:
        """Test for carrier presence using RPD."""
        self.set_channel(channel)
        radio = self._require_initialized()
        with self._lock:
            return radio.testCarrier()
    
    def test_rpd(self, channel: int) -> bool:
        """Test Received Power Detector."""
        self.set_channel(channel)
        radio = self._require_initialized()
        with self._lock:
            return radio.testRPD()
    
    def get_rpd_value(self, channel: int) -> int:
        """Get raw RPD value (0-255)."""
        self.set_channel(channel)
        radio = self._require_initialized()
        with self._lock:
            return radio.getRPD()
    
    def get_rpd_db(self, channel: int) -> float:
        """Get signal strength in dBm from RPD."""
        rpd = self.get_rpd_value(channel)
        return (rpd / 255.0) * 60.0 - 100.0
    
    def sweep_all_channels(self, progress_callback=None) -> list[float]:
        """Sweep all channels and return dBm values."""
        results = [0.0] * (self._config.channel_max - self._config.channel_min + 1)
        
        for i, ch in enumerate(range(self._config.channel_min, self._config.channel_max + 1)):
            try:
                results[i] = self.get_rpd_db(ch)
            except RadioOperationError:
                results[i] = -100.0
            
            if progress_callback:
                progress_callback(i + 1, len(results))
        
        return results
    
    def transmit_carrier(self, channel: int, duration_ms: int = 100) -> bool:
        """Transmit continuous carrier wave."""
        if duration_ms <= 0 or duration_ms > 10000:
            raise ValueError("Duration must be 1-10000 ms")
        
        self.set_channel(channel)
        radio = self._require_initialized()
        
        with self._lock:
            try:
                radio.txStandBy()
                radio.write(b'\x00' * 32)
                time.sleep(duration_ms / 1000.0)
                return True
            except Exception as e:
                logger.error(f"Carrier transmit failed: {e}")
                raise RadioOperationError(f"Transmit failed: {e}") from e
    
    def transmit_noise(self, channel: int, packets: int = 100) -> bool:
        """Transmit high-rate packet noise."""
        if packets <= 0 or packets > 10000:
            raise ValueError("Packets must be 1-10000")
        
        self.set_channel(channel)
        radio = self._require_initialized()
        payload = bytes([0xAA, 0x55] * 16)
        
        with self._lock:
            try:
                for _ in range(packets):
                    radio.write(payload)
                    time.sleep(0.0001)
                return True
            except Exception as e:
                logger.error(f"Noise transmit failed: {e}")
                raise RadioOperationError(f"Transmit failed: {e}") from e
    
    def channel_to_freq(self, channel: int) -> float:
        return self._config.freq_base_mhz + channel
    
    def freq_to_channel(self, freq_mhz: float) -> int:
        ch = int(freq_mhz - self._config.freq_base_mhz)
        return max(self._config.channel_min, min(self._config.channel_max, ch))
    
    def cleanup(self):
        """Power down and release resources."""
        with self._lock:
            if self._radio and self._initialized:
                try:
                    self._radio.powerDown()
                except Exception:
                    pass
                self._initialized = False
                self._radio = None
    
    def __enter__(self):
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False


class RadioFactory:
    """Factory for creating radio instances with fallback."""
    
    @staticmethod
    def create_hardware(config: Optional[RadioConfig] = None) -> Tuple[HardwareRadio, bool]:
        """Create and initialize hardware radio. Returns (radio, success)."""
        radio = HardwareRadio(config)
        success = radio.initialize()
        return radio, success
    
    @staticmethod
    def create_with_fallback(config: Optional[RadioConfig] = None, 
                              force_hardware: bool = False) -> "RadioInterface":
        """Create hardware radio, fall back to simulation on failure."""
        from sim_radio import SimRadio
        
        if force_hardware:
            radio, success = RadioFactory.create_hardware(config)
            if not success:
                raise RadioInitError(radio.last_error or "Hardware init failed")
            return radio
        
        radio, success = RadioFactory.create_hardware(config)
        if success:
            logger.info("Using hardware radio")
            return radio
        
        logger.warning(f"Hardware init failed ({radio.last_error}), falling back to simulation")
        sim = SimRadio()
        sim.initialize()
        return sim


class RadioInterface:
    """Common interface for hardware and simulation radios."""
    
    def initialize(self) -> bool: ...
    def set_channel(self, channel: int) -> bool: ...
    def get_rpd_value(self, channel: int) -> int: ...
    def get_rpd_db(self, channel: int) -> float: ...
    def transmit_carrier(self, channel: int, duration_ms: int) -> bool: ...
    def transmit_noise(self, channel: int, packets: int) -> bool: ...
    def cleanup(self): ...


# Make HardwareRadio implement the interface
HardwareRadio.__bases__ = (RadioInterface,) + HardwareRadio.__bases__