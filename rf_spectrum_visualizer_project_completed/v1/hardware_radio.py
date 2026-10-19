import time
import threading
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from pyrf24 import RF24, RF24_PA_LOW, RF24_PA_HIGH, RF24_250KBPS, RF24_1MBPS, RF24_2MBPS
    PYRF24_AVAILABLE = True
except ImportError:
    PYRF24_AVAILABLE = False
    RF24 = None
    RF24_PA_LOW = RF24_PA_HIGH = RF24_250KBPS = RF24_1MBPS = RF24_2MBPS = None


class HardwareRadio:
    """Interfaces with nRF24L01+ transceiver over SPI for 2.4 GHz ISM band scanning."""
    
    CHANNEL_MIN = 0
    CHANNEL_MAX = 125
    FREQ_BASE_MHZ = 2400
    SPI_SPEED_HZ = 10_000_000
    
    def __init__(self, ce_pin: int = 25, csn_pin: int = 8, spi_speed: int = SPI_SPEED_HZ, spi_device: str = "/dev/spidev0.0"):
        self.ce_pin = ce_pin
        self.csn_pin = csn_pin
        self.spi_speed = spi_speed
        self.spi_device = spi_device
        self._radio: Optional[RF24] = None
        self._lock = threading.Lock()
        self._initialized = False
        
    def initialize(self) -> bool:
        """Initialize the nRF24L01+ hardware via SPI."""
        if not PYRF24_AVAILABLE:
            logger.error("pyrf24 library not available")
            return False
            
        with self._lock:
            if self._initialized:
                return True
                
            try:
                self._radio = RF24(self.ce_pin, self.csn_pin, self.spi_speed, self.spi_device)
                if not self._radio.begin():
                    logger.error("Failed to initialize nRF24L01+ radio")
                    return False
                    
                self._radio.setPALevel(RF24_PA_LOW)
                self._radio.setDataRate(RF24_2MBPS)
                self._radio.setAutoAck(False)
                self._radio.setRetries(0, 0)
                self._radio.setChannel(0)
                self._radio.powerUp()
                self._radio.flush_rx()
                self._radio.flush_tx()
                
                self._initialized = True
                logger.info("nRF24L01+ initialized successfully")
                return True
                
            except Exception as e:
                logger.error(f"Hardware initialization failed: {e}")
                self._radio = None
                return False
    
    def set_channel(self, channel: int) -> bool:
        """Set radio to specific channel (0-125)."""
        if not self._initialized or self._radio is None:
            return False
        if not (self.CHANNEL_MIN <= channel <= self.CHANNEL_MAX):
            return False
            
        with self._lock:
            try:
                self._radio.setChannel(channel)
                time.sleep(0.00013)  # 130us settling time per datasheet
                return True
            except Exception as e:
                logger.error(f"Failed to set channel {channel}: {e}")
                return False
    
    def test_carrier(self, channel: int) -> bool:
        """Test for carrier presence on channel using RPD register."""
        if not self.set_channel(channel):
            return False
            
        with self._lock:
            try:
                return self._radio.testCarrier()
            except Exception as e:
                logger.error(f"Carrier test failed on channel {channel}: {e}")
                return False
    
    def test_rpd(self, channel: int) -> bool:
        """Test Received Power Detector on channel."""
        if not self.set_channel(channel):
            return False
            
        with self._lock:
            try:
                return self._radio.testRPD()
            except Exception as e:
                logger.error(f"RPD test failed on channel {channel}: {e}")
                return False
    
    def get_rpd_value(self, channel: int) -> int:
        """Get raw RPD value (0-255) for signal strength estimation."""
        if not self.set_channel(channel):
            return 0
            
        with self._lock:
            try:
                return self._radio.getRPD()
            except Exception as e:
                logger.error(f"RPD read failed on channel {channel}: {e}")
                return 0
    
    def transmit_carrier(self, channel: int, duration_ms: int = 100) -> bool:
        """Transmit continuous carrier wave on channel for mitigation."""
        if not self._initialized or self._radio is None:
            return False
            
        with self._lock:
            try:
                self._radio.setChannel(channel)
                self._radio.txStandBy()
                self._radio.write(b'\x00' * 32)  # Dummy payload
                time.sleep(duration_ms / 1000.0)
                return True
            except Exception as e:
                logger.error(f"Carrier transmit failed: {e}")
                return False
    
    def transmit_noise(self, channel: int, packets: int = 100) -> bool:
        """Transmit high-rate packet noise for active jamming mitigation."""
        if not self._initialized or self._radio is None:
            return False
            
        with self._lock:
            try:
                self._radio.setChannel(channel)
                payload = bytes([0xAA, 0x55] * 16)
                for _ in range(packets):
                    self._radio.write(payload)
                    time.sleep(0.0001)
                return True
            except Exception as e:
                logger.error(f"Noise transmit failed: {e}")
                return False
    
    def channel_to_freq(self, channel: int) -> float:
        """Convert channel number to frequency in MHz."""
        return self.FREQ_BASE_MHZ + channel
    
    def freq_to_channel(self, freq_mhz: float) -> int:
        """Convert frequency in MHz to channel number."""
        return max(self.CHANNEL_MIN, min(self.CHANNEL_MAX, int(freq_mhz - self.FREQ_BASE_MHZ)))
    
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