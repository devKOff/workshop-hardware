#!/usr/bin/env python3
"""Check pyrf24 API availability and compatibility for v6."""

import sys
import subprocess
from typing import Dict, Any, List


def check_pyrf24_installation() -> Dict[str, Any]:
    """Check pyrf24 installation details."""
    result = {
        "installed": False,
        "version": None,
        "location": None,
        "attributes": [],
        "methods": [],
        "errors": [],
    }
    
    try:
        import pyrf24
        result["installed"] = True
        result["version"] = getattr(pyrf24, "__version__", "unknown")
        result["location"] = getattr(pyrf24, "__file__", "unknown")
        
        # Check key classes and methods
        if hasattr(pyrf24, "RF24"):
            rf24 = pyrf24.RF24
            result["attributes"].append("RF24 class found")
            
            # Check methods
            methods_to_check = [
                "begin", "setChannel", "testRPD", "setPALevel", "setDataRate",
                "setCRCLength", "setAutoAck", "stopListening", "powerDown",
                "getPALevel", "getDataRate", "getCRCLength", "isPVariant",
                "setRetries", "setAddressWidth", "openWritingPipe", "openReadingPipe",
            ]
            
            for method in methods_to_check:
                if hasattr(rf24, method):
                    result["methods"].append(method)
                else:
                    result["errors"].append(f"Missing method: RF24.{method}")
        
        # Check constants
        constants_to_check = [
            "RF24_PA_LOW", "RF24_PA_HIGH", "RF24_PA_MAX",
            "RF24_1MBPS", "RF24_2MBPS", "RF24_250KBPS",
            "RF24_CRC_16", "RF24_CRC_8", "RF24_CRC_DISABLED",
        ]
        
        for const in constants_to_check:
            if hasattr(pyrf24, const):
                result["attributes"].append(f"Constant: {const}")
            else:
                result["errors"].append(f"Missing constant: {const}")
        
    except ImportError as e:
        result["errors"].append(f"ImportError: {e}")
    except Exception as e:
        result["errors"].append(f"Unexpected error: {e}")
    
    return result


def check_spi_availability() -> Dict[str, Any]:
    """Check SPI device availability."""
    import os
    result = {
        "devices": [],
        "errors": [],
    }
    
    try:
        for bus in range(2):
            for device in range(2):
                path = f"/dev/spidev{bus}.{device}"
                if os.path.exists(path):
                    result["devices"].append(path)
        
        if not result["devices"]:
            result["errors"].append("No SPI devices found. Enable SPI in raspi-config")
    except Exception as e:
        result["errors"].append(f"SPI check failed: {e}")
    
    return result


def check_gpio_access() -> Dict[str, Any]:
    """Check GPIO memory access."""
    import os
    result = {
        "gpiomem_access": False,
        "gpiochip_access": [],
        "errors": [],
    }
    
    try:
        result["gpiomem_access"] = os.access("/dev/gpiomem", os.R_OK | os.W_OK)
    except Exception:
        pass
    
    try:
        import glob
        for chip in glob.glob("/dev/gpiochip*"):
            result["gpiochip_access"].append(chip)
    except Exception:
        pass
    
    return result


def test_radio_initialization(ce_pin: int = 25, csn_pin: int = 0) -> Dict[str, Any]:
    """Test actual radio initialization."""
    result = {
        "success": False,
        "info": None,
        "errors": [],
    }
    
    try:
        import pyrf24
        radio = pyrf24.RF24(ce_pin, csn_pin)
        
        if not radio.begin():
            result["errors"].append("radio.begin() returned False - check wiring")
            return result
        
        radio.setPALevel(pyrf24.RF24_PA_LOW)
        radio.setDataRate(pyrf24.RF24_1MBPS)
        radio.setCRCLength(pyrf24.RF24_CRC_16)
        radio.setAutoAck(False)
        radio.stopListening()
        
        result["info"] = {
            "channel": radio.getChannel() if hasattr(radio, "getChannel") else "unknown",
            "pa_level": radio.getPALevel(),
            "data_rate": radio.getDataRate(),
            "crc_length": radio.getCRCLength(),
            "is_pvariant": radio.isPVariant() if hasattr(radio, "isPVariant") else "unknown",
        }
        
        radio.powerDown()
        result["success"] = True
        
    except Exception as e:
        result["errors"].append(f"Initialization failed: {e}")
    
    return result


def main() -> int:
    print("=" * 60)
    print("pyrf24 API Check for RF Spectrum Visualizer v6")
    print("=" * 60)
    
    # Check installation
    print("\n1. pyrf24 Installation:")
    install_result = check_pyrf24_installation()
    print(f"   Installed: {install_result['installed']}")
    if install_result["installed"]:
        print(f"   Version: {install_result['version']}")
        print(f"   Location: {install_result['location']}")
        print(f"   Available methods: {len(install_result['methods'])}")
        for method in install_result["methods"]:
            print(f"     - {method}")
    if install_result["errors"]:
        print("   Errors:")
        for err in install_result["errors"]:
            print(f"     - {err}")
    
    # Check SPI
    print("\n2. SPI Devices:")
    spi_result = check_spi_availability()
    if spi_result["devices"]:
        for dev in spi_result["devices"]:
            print(f"   - {dev}")
    else:
        print("   None found")
    for err in spi_result["errors"]:
        print(f"   Error: {err}")
    
    # Check GPIO
    print("\n3. GPIO Access:")
    gpio_result = check_gpio_access()
    print(f"   /dev/gpiomem: {'OK' if gpio_result['gpiomem_access'] else 'NO ACCESS'}")
    if gpio_result["gpiochip_access"]:
        for chip in gpio_result["gpiochip_access"]:
            print(f"   - {chip}")
    
    # Test initialization if available
    if install_result["installed"] and spi_result["devices"]:
        print("\n4. Hardware Initialization Test:")
        print("   Testing with CE=GPIO25, CSN=GPIO8 (SPI CE0)...")
        init_result = test_radio_initialization(25, 0)
        if init_result["success"]:
            print("   SUCCESS - Radio initialized")
            for k, v in init_result["info"].items():
                print(f"     {k}: {v}")
        else:
            print("   FAILED")
            for err in init_result["errors"]:
                print(f"     - {err}")
    else:
        print("\n4. Hardware Initialization Test: SKIPPED (missing dependencies)")
    
    print("\n" + "=" * 60)
    print("Check complete")
    print("=" * 60)
    
    return 0 if install_result["installed"] else 1


if __name__ == "__main__":
    sys.exit(main())