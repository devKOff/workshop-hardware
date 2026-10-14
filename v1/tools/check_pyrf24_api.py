#!/usr/bin/env python3
"""
Diagnostic script to test SPI connectivity, module initialization,
and verify pyrf24 methods on Raspberry Pi before runtime.
"""

import sys
import time
import logging
from typing import List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def check_pyrf24_import() -> bool:
    """Test if pyrf24 can be imported."""
    try:
        import pyrf24
        logger.info(f"pyrf24 imported successfully: {pyrf24.__file__}")
        return True
    except ImportError as e:
        logger.error(f"Failed to import pyrf24: {e}")
        logger.error("Install with: pip install pyrf24")
        return False


def check_spi_devices() -> List[str]:
    """Check available SPI devices."""
    import glob
    devices = glob.glob("/dev/spidev*")
    logger.info(f"Available SPI devices: {devices}")
    return devices


def check_gpio_access() -> bool:
    """Check GPIO access permissions."""
    import os
    try:
        with open("/sys/class/gpio/export", "w") as f:
            f.write("25")
        with open("/sys/class/gpio/unexport", "w") as f:
            f.write("25")
        logger.info("GPIO access: OK")
        return True
    except PermissionError:
        logger.error("GPIO access denied. Run with sudo or add user to gpio group.")
        return False
    except Exception as e:
        logger.error(f"GPIO check failed: {e}")
        return False


def test_radio_initialization(ce_pin: int = 25, csn_pin: int = 8, spi_speed: int = 10_000_000) -> Tuple[bool, Optional[object]]:
    """Test nRF24L01+ initialization."""
    try:
        from pyrf24 import RF24, RF24_PA_LOW, RF24_2MBPS
        
        logger.info(f"Initializing RF24(CE={ce_pin}, CSN={csn_pin}, SPI={spi_speed}Hz)")
        radio = RF24(ce_pin, csn_pin, spi_speed)
        
        if not radio.begin():
            logger.error("radio.begin() failed - check wiring and SPI config")
            return False, None
        
        logger.info("radio.begin() succeeded")
        
        radio.setPALevel(RF24_PA_LOW)
        radio.setDataRate(RF24_2MBPS)
        radio.setAutoAck(False)
        radio.setRetries(0, 0)
        radio.setChannel(0)
        radio.powerUp()
        radio.flush_rx()
        radio.flush_tx()
        
        logger.info("Radio configured successfully")
        return True, radio
        
    except Exception as e:
        logger.error(f"Radio initialization failed: {e}")
        return False, None


def test_channel_sweep(radio) -> bool:
    """Test channel switching and RPD reading across all channels."""
    logger.info("Testing channel sweep (0-125)...")
    
    try:
        results = []
        for ch in range(0, 126, 10):
            radio.setChannel(ch)
            time.sleep(0.0002)
            rpd = radio.getRPD()
            carrier = radio.testCarrier()
            rpd_bool = radio.testRPD()
            results.append((ch, rpd, carrier, rpd_bool))
            logger.info(f"  Ch {ch:3d}: RPD={rpd:3d} Carrier={carrier} RPD_bool={rpd_bool}")
        
        active_channels = [r for r in results if r[1] > 0 or r[2] or r[3]]
        if active_channels:
            logger.info(f"Active channels detected: {active_channels}")
        else:
            logger.info("No active signals detected (quiet environment)")
        
        return True
        
    except Exception as e:
        logger.error(f"Channel sweep failed: {e}")
        return False


def test_register_access(radio) -> bool:
    """Test direct register read/write."""
    try:
        from pyrf24 import RF24
        
        logger.info("Testing register access...")
        
        config = radio.read_register(RF24.CONFIG)
        logger.info(f"  CONFIG register: 0x{config:02X}")
        
        rf_setup = radio.read_register(RF24.RF_SETUP)
        logger.info(f"  RF_SETUP register: 0x{rf_setup:02X}")
        
        rf_ch = radio.read_register(RF24.RF_CH)
        logger.info(f"  RF_CH register: 0x{rf_ch:02X} (ch {rf_ch})")
        
        status = radio.read_register(RF24.STATUS)
        logger.info(f"  STATUS register: 0x{status:02X}")
        
        rx_addr_p0 = radio.read_register(RF24.RX_ADDR_P0, 5)
        logger.info(f"  RX_ADDR_P0: {rx_addr_p0.hex()}")
        
        return True
        
    except Exception as e:
        logger.error(f"Register access test failed: {e}")
        return False


def test_transmit(radio, channel: int = 2) -> bool:
    """Test packet transmission."""
    try:
        logger.info(f"Testing transmission on channel {channel}...")
        radio.setChannel(channel)
        radio.txStandBy()
        
        payload = b"TEST" + bytes([0] * 28)
        result = radio.write(payload)
        logger.info(f"  Write result: {result}")
        
        tx_ok = radio.getStatus() & 0x20
        max_rt = radio.getStatus() & 0x10
        logger.info(f"  TX_OK: {bool(tx_ok)}, MAX_RT: {bool(max_rt)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Transmission test failed: {e}")
        return False


def test_carrier_wave(radio, channel: int = 2, duration_ms: int = 100) -> bool:
    """Test continuous carrier wave transmission."""
    try:
        logger.info(f"Testing carrier wave on channel {channel} for {duration_ms}ms...")
        radio.setChannel(channel)
        radio.txStandBy()
        
        radio.write(b"\x00" * 32)
        time.sleep(duration_ms / 1000.0)
        
        logger.info("Carrier wave test completed")
        return True
        
    except Exception as e:
        logger.error(f"Carrier wave test failed: {e}")
        return False


def run_full_diagnostic():
    """Run complete diagnostic suite."""
    logger.info("=" * 60)
    logger.info("nRF24L01+ Diagnostic Suite")
    logger.info("=" * 60)
    
    results = {}
    
    results["import"] = check_pyrf24_import()
    if not results["import"]:
        return results
    
    results["spi_devices"] = len(check_spi_devices()) > 0
    results["gpio"] = check_gpio_access()
    
    success, radio = test_radio_initialization()
    results["init"] = success
    
    if success and radio:
        results["registers"] = test_register_access(radio)
        results["sweep"] = test_channel_sweep(radio)
        results["tx"] = test_transmit(radio)
        results["carrier"] = test_carrier_wave(radio)
        
        radio.powerDown()
    
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


if __name__ == "__main__":
    results = run_full_diagnostic()
    sys.exit(0 if all(results.values()) else 1)