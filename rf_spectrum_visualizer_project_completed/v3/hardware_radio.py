"""Hardware backend for nRF24L01+ radio using pyrf24."""

import time
import threading
import logging
from typing import Optional, Tuple
from contextlib import contextmanager

from config import ChannelConfig, ScanConfig
from exceptions import (
    HardwareError,
    RadioInitializationError,
    SPIError,
    RadioNotFoundError,
    InvalidChannelError,
)

logger = logging.getLogger("rf_visualizer.hardware")


class HardwareRadio:
    """Hardware interface for nRF24L01+ via pyrf24."""
    
    def __init__(
        self,
        channel_config: ChannelConfig,
        scan_config: ScanConfig,
        ce_pin: int = 25,
        csn_pin: int = 0,  # SPI CE0
        spi_speed: int = 4_000_000,
    ):
        self._channel_config = channel_config
        self._scan_config = scan_config
        self._ce_pin = ce_pin
        self._csn_pin = csn_pin
        self._spi_speed = spi_speed
        self._radio = None
        self._initialized = False
        self._lock = threading.RLock()
        self._current_channel = channel_config.start_channel
        self._pyrf24_available = False
        self._check_pyrf24()
    
    def _check_pyrf24(self) -> None:
        """Check if pyrf24 is available and get version info."""
        try:
            import pyrf24
            self._pyrf24 = pyrf24
            self._pyrf24_available = True
            logger.info(f"pyrf24 available: {getattr(pyrf24, '__version__', 'unknown version')}")
        except ImportError:
            self._pyrf24 = None
            self._pyrf24_available = False
            logger.warning("pyrf24 not installed - hardware mode unavailable")
    
    def is_available(self) -> bool:
        """Check if hardware backend is available."""
        return self._pyrf24_available
    
    def initialize(self) -> bool:
        """Initialize the nRF24L01+ radio."""
        with self._lock:
            if not self._pyrf24_available:
                raise RadioInitializationError("pyrf24 library not available")
            
            try:
                self._radio = self._pyrf24.RF24(self._ce_pin, self._csn_pin)
                
                if not self._radio.begin():
                    raise RadioNotFoundError(
                        "nRF24L01+ not responding. Check wiring: "
                        f"CE=GPIO{self._ce_pin}, CSN=SPI CE{self._csn_pin}, "
                        "SCK=GPIO11, MOSI=GPIO10, MISO=GPIO9, 3.3V, GND"
                    )
                
                self._radio.setPALevel(self._pyrf24.RF24_PA_LOW)
                self._radio.setDataRate(self._pyrf24.RF24_1MBPS)
                self._radio.setCRCLength(self._pyrf24.RF24_CRC_16)
                self._radio.setAutoAck(False)
                self._radio.stopListening()
                
                self._current_channel = self._channel_config.start_channel
                self._radio.setChannel(self._current_channel)
                
                self._initialized = True
                logger.info(f"nRF24L01+ initialized on channel {self._current_channel}")
                return True
                
            except Exception as e:
                if "SPI" in str(type(e)).upper() or "spi" in str(e).lower():
                    raise SPIError(f"SPI initialization failed: {e}") from e
                raise RadioInitializationError(f"Failed to initialize radio: {e}") from e
    
    def is_initialized(self) -> bool:
        return self._initialized
    
    def set_channel(self, channel: int) -> None:
        """Set the radio channel."""
        with self._lock:
            if not self._initialized:
                raise HardwareError("Radio not initialized")
            if not self._channel_config.start_channel <= channel <= self._channel_config.end_channel:
                raise InvalidChannelError(
                    f"Channel {channel} out of range "
                    f"({self._channel_config.start_channel}-{self._channel_config.end_channel})"
                )
            
            self._current_channel = channel
            self._radio.setChannel(channel)
            time.sleep(0.00013)  # 130µs channel switch delay per datasheet
    
    def get_channel(self) -> int:
        """Get the current channel."""
        with self._lock:
            return self._current_channel
    
    def read_rpd(self) -> bool:
        """Read RPD (Received Power Detector) status."""
        with self._lock:
            if not self._initialized:
                raise HardwareError("Radio not initialized")
            
            try:
                return bool(self._radio.testRPD())
            except Exception as e:
                raise HardwareError(f"RPD read failed: {e}") from e
    
    def scan_channel(
        self,
        channel: int,
        duration: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> Tuple[int, int, int]:
        """
        Scan a channel for RPD activity.
        
        Returns:
            Tuple of (valid_samples, rpd_positive, rpd_negative)
        """
        with self._lock:
            if not self._initialized:
                raise HardwareError("Radio not initialized")
            
            duration = duration or self._scan_config.measurement_window
            interval = interval or self._scan_config.sampling_interval
            
            self.set_channel(channel)
            samples = int(duration / interval)
            valid = 0
            positive = 0
            negative = 0
            
            start_time = time.monotonic()
            for i in range(samples):
                try:
                    rpd = self.read_rpd()
                    valid += 1
                    if rpd:
                        positive += 1
                    else:
                        negative += 1
                except HardwareError:
                    pass
                
                elapsed = time.monotonic() - start_time
                expected = (i + 1) * interval
                sleep_time = expected - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            return valid, positive, negative
    
    def cleanup(self) -> None:
        """Clean up radio resources."""
        with self._lock:
            if self._radio and self._initialized:
                try:
                    self._radio.powerDown()
                except Exception as e:
                    logger.warning(f"Error during radio cleanup: {e}")
            self._initialized = False
            self._radio = None
    
    def get_info(self) -> dict:
        """Get radio information for diagnostics."""
        with self._lock:
            if not self._initialized:
                return {"initialized": False}
            
            try:
                return {
                    "initialized": True,
                    "channel": self._current_channel,
                    "pa_level": self._radio.getPALevel(),
                    "data_rate": self._radio.getDataRate(),
                    "crc_length": self._radio.getCRCLength(),
                    "is_pv": self._radio.isPVariant(),
                }
            except Exception as e:
                return {"initialized": True, "error": str(e)}
    
    @contextmanager
    def locked(self):
        """Context manager for exclusive radio access."""
        self._lock.acquire()
        try:
            yield self
        finally:
            self._lock.release()


def check_hardware_availability() -> dict:
    """Check hardware availability without initializing radio."""
    result = {
        "pyrf24_installed": False,
        "pyrf24_version": None,
        "spi_devices": [],
        "gpio_access": False,
        "errors": [],
    }
    
    try:
        import pyrf24
        result["pyrf24_installed"] = True
        result["pyrf24_version"] = getattr(pyrf24, "__version__", "unknown")
    except ImportError as e:
        result["errors"].append(f"pyrf24 not installed: {e}")
    
    try:
        import spidev
        for bus in range(2):
            for device in range(2):
                path = f"/dev/spidev{bus}.{device}"
                import os
                if os.path.exists(path):
                    result["spi_devices"].append(path)
    except ImportError:
        result["errors"].append("spidev not installed")
    except Exception as e:
        result["errors"].append(f"SPI check failed: {e}")
    
    try:
        import os
        result["gpio_access"] = os.access("/dev/gpiomem", os.R_OK | os.W_OK)
    except Exception:
        pass
    
    return result