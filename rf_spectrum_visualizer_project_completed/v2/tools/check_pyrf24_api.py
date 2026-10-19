"""Diagnostic script for nRF24L01+ hardware verification."""
import sys
import time
import logging
from typing import List, Tuple, Optional

from config import RadioConfig
from hardware_radio import HardwareRadio, RadioInitError, PYRF24_AVAILABLE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def check_pyrf24_import() -> bool:
    """Test if pyrf24 can be imported."""
    if not PYRF24_AVAILABLE:
        logger.error("pyrf24 library not available")
        logger.error("Install with: pip install pyrf24")
        return False
    
    import pyrf24
    logger.info(f"pyrf24 imported: {pyrf24.__file__}")
    return True


def check_spi_devices() -> List[str]:
    """Check available SPI devices."""
    import glob
    devices = glob.glob("/dev/spidev*")
    logger.info(f"Available SPI devices: {devices}")
    return devices


def check_gpio_access() -> bool:
    """Check GPIO access permissions."""
    try:
        import subprocess
        result = subprocess.run(["gpio", "readall"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("GPIO access: OK (via gpio utility)")
            return True
    except FileNotFoundError:
        pass
    
    # Try sysfs
    try:
        with open("/sys/class/gpio/export", "w") as f:
            f.write("25")
        with open("/sys/class/gpio/unexport", "w") as f:
            f.write("25")
        logger.info("GPIO access: OK (sysfs)")
        return True
    except PermissionError:
        logger.error("GPIO access denied. Run with sudo or add user to gpio group.")
        return False
    except Exception as e:
        logger.warning(f"GPIO check via sysfs failed: {e}")
    
    return True  # Not fatal


def test_radio_initialization(config: RadioConfig) -> Tuple[bool, Optional[HardwareRadio]]:
    """Test nRF24L01+ initialization."""
    logger.info(f"Initializing RF24(CE={config.ce_pin}, CSN={config.csn_pin}, "
                f"SPI={config.spi_speed_hz}Hz, device={config.spi_device})")
    
    radio = HardwareRadio(config)
    if not radio.initialize():
        logger.error(f"radio.initialize() failed: {radio.last_error}")
        return False, None
    
    logger.info("radio.initialize() succeeded")
    return True, radio


def test_register_access(radio: HardwareRadio) -> bool:
    """Test direct register read/write."""
    try:
        from pyrf24 import RF24
        
        logger.info("Testing register access...")
        
        config_reg = radio._radio.read_register(RF24.CONFIG)
        logger.info(f"  CONFIG register: 0x{config_reg:02X}")
        
        rf_setup = radio._radio.read_register(RF24.RF_SETUP)
        logger.info(f"  RF_SETUP register: 0x{rf_setup:02X}")
        
        rf_ch = radio._radio.read_register(RF24.RF_CH)
        logger.info(f"  RF_CH register: 0x{rf_ch:02X} (ch {rf_ch})")
        
        status = radio._radio.read_register(RF24.STATUS)
        logger.info(f"  STATUS register: 0x{status:02X}")
        
        return True
        
    except Exception as e:
        logger.error(f"Register access test failed: {e}")
        return False


def test_channel_sweep(radio: HardwareRadio) -> bool:
    """Test channel switching and RPD reading across all channels."""
    logger.info("Testing channel sweep (0-125)...")
    
    try:
        results = []
        for ch in range(0, 126, 10):
            rpd = radio.get_rpd_value(ch)
            carrier = radio.test_carrier(ch)
            rpd_bool = radio.test_rpd(ch)
            results.append((ch, rpd, carrier, rpd_bool))
            logger.info(f"  Ch {ch:3d}: RPD={rpd:3d} Carrier={carrier} RPD_bool={rpd_bool}")
        
        active_channels = [r for r in results if r[1] > 0 or r[2] or r[3]]
        if active_channels:
            logger.info(f"Active channels detected: {len(active_channels)}")
        else:
            logger.info("No active signals detected (quiet environment)")
        
        return True
        
    except Exception as e:
        logger.error(f"Channel sweep failed: {e}")
        return False


def test_transmit(radio: HardwareRadio, channel: int = 2) -> bool:
    """Test packet transmission."""
    try:
        logger.info(f"Testing transmission on channel {channel}...")
        success = radio.transmit_carrier(channel, 100)
        logger.info(f"  Carrier transmit: {success}")
        return success
        
    except Exception as e:
        logger.error(f"Transmission test failed: {e}")
        return False


def test_carrier_wave(radio: HardwareRadio, channel: int = 2, duration_ms: int = 100) -> bool:
    """Test continuous carrier wave transmission."""
    try:
        logger.info(f"Testing carrier wave on channel {channel} for {duration_ms}ms...")
        success = radio.transmit_carrier(channel, duration_ms)
        logger.info("Carrier wave test completed")
        return success
        
    except Exception as e:
        logger.error(f"Carrier wave test failed: {e}")
        return False


def test_noise_transmit(radio: HardwareRadio, channel: int = 2, packets: int = 50) -> bool:
    """Test packet noise transmission."""
    try:
        logger.info(f"Testing noise transmit on channel {channel} ({packets} packets)...")
        success = radio.transmit_noise(channel, packets)
        logger.info("Noise transmit test completed")
        return success
        
    except Exception as e:
        logger.error(f"Noise transmit test failed: {e}")
        return False


def run_full_diagnostic(config: Optional[RadioConfig] = None) -> dict:
    """Run complete diagnostic suite."""
    config = config or RadioConfig()
    
    logger.info("=" * 60)
    logger.info("nRF24L01+ Diagnostic Suite v2")
    logger.info("=" * 60)
    
    results = {}
    
    results["import"] = check_pyrf24_import()
    if not results["import"]:
        return results
    
    results["spi_devices"] = len(check_spi_devices()) > 0
    results["gpio"] = check_gpio_access()
    
    success, radio = test_radio_initialization(config)
    results["init"] = success
    
    if success and radio:
        results["registers"] = test_register_access(radio)
        results["sweep"] = test_channel_sweep(radio)
        results["tx_carrier"] = test_transmit(radio)
        results["carrier_wave"] = test_carrier_wave(radio)
        results["noise_tx"] = test_noise_transmit(radio)
        
        radio.cleanup()
    
    logger.info("=" * 60)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"  {test:15s}: {status}")
    
    all_pass = all(results.values())
    logger.info("=" * 60)
    if all_pass:
        logger.info("ALL TESTS PASSED - Hardware ready for operation")
    else:
        logger.error("SOME TESTS FAILED - Check hardware connections")
    logger.info("=" * 60)
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="nRF24L01+ Hardware Diagnostic v2")
    parser.add_argument("--ce", type=int, default=25, help="CE pin (default: 25)")
    parser.add_argument("--csn", type=int, default=8, help="CSN pin (default: 8)")
    parser.add_argument("--spi", type=int, default=10_000_000, help="SPI speed Hz (default: 10MHz)")
    parser.add_argument("--device", type=str, default="/dev/spidev0.0", help="SPI device path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    config = RadioConfig(
        ce_pin=args.ce,
        csn_pin=args.csn,
        spi_speed_hz=args.spi,
        spi_device=args.device,
    )
    
    results = run_full_diagnostic(config)
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()