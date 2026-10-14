#!/usr/bin/env python3
"""pyrf24 API diagnostic tool for RF Spectrum Visualizer."""

import sys
import platform
import subprocess
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("check_pyrf24")


def check_python_version() -> Dict[str, Any]:
    """Check Python version."""
    return {
        "version": sys.version,
        "version_info": sys.version_info[:3],
        "acceptable": sys.version_info >= (3, 7),
    }


def check_pyrf24_installation() -> Dict[str, Any]:
    """Check pyrf24 installation and API."""
    result = {
        "installed": False,
        "version": None,
        "location": None,
        "classes": {},
        "methods": {},
        "constants": {},
        "errors": [],
    }
    
    try:
        import pyrf24
        result["installed"] = True
        result["version"] = getattr(pyrf24, "__version__", "unknown")
        result["location"] = getattr(pyrf24, "__file__", "unknown")
        
        expected_classes = ["RF24", "RF24Network", "RF24Mesh"]
        for cls_name in expected_classes:
            cls = getattr(pyrf24, cls_name, None)
            result["classes"][cls_name] = cls is not None
            if cls:
                methods = [m for m in dir(cls) if not m.startswith("_")]
                result["methods"][cls_name] = methods
        
        expected_constants = [
            "RF24_PA_MIN", "RF24_PA_LOW", "RF24_PA_HIGH", "RF24_PA_MAX",
            "RF24_250KBPS", "RF24_1MBPS", "RF24_2MBPS",
            "RF24_CRC_DISABLED", "RF24_CRC_8", "RF24_CRC_16",
        ]
        for const in expected_constants:
            result["constants"][const] = hasattr(pyrf24, const)
        
        if "RF24" in result["methods"]:
            rf24_methods = result["methods"]["RF24"]
            critical_methods = [
                "begin", "setChannel", "getChannel", "testRPD",
                "setPALevel", "getPALevel", "setDataRate", "getDataRate",
                "setCRCLength", "getCRCLength", "stopListening", "startListening",
                "powerUp", "powerDown", "isPVariant", "write", "read",
                "available", "flush_tx", "flush_rx",
            ]
            for method in critical_methods:
                result["methods"][f"RF24.{method}"] = method in rf24_methods
    
    except ImportError as e:
        result["errors"].append(f"ImportError: {e}")
    except Exception as e:
        result["errors"].append(f"Unexpected error: {e}")
    
    return result


def check_spi_devices() -> Dict[str, Any]:
    """Check available SPI devices."""
    result = {
        "devices": [],
        "accessible": [],
        "errors": [],
    }
    
    import os
    for bus in range(2):
        for device in range(2):
            path = f"/dev/spidev{bus}.{device}"
            if os.path.exists(path):
                result["devices"].append(path)
                try:
                    import spidev
                    spi = spidev.SpiDev()
                    spi.open(bus, device)
                    spi.close()
                    result["accessible"].append(path)
                except Exception as e:
                    result["errors"].append(f"{path}: {e}")
    
    return result


def check_gpio_access() -> Dict[str, Any]:
    """Check GPIO access."""
    result = {
        "gpiomem_accessible": False,
        "gpiochip_accessible": False,
        "errors": [],
    }
    
    import os
    result["gpiomem_accessible"] = os.access("/dev/gpiomem", os.R_OK | os.W_OK)
    
    try:
        result["gpiochip_accessible"] = os.access("/dev/gpiochip0", os.R_OK | os.W_OK)
    except Exception:
        pass
    
    return result


def attempt_hardware_init(read_only: bool = True) -> Dict[str, Any]:
    """Attempt to initialize hardware radio."""
    result = {
        "attempted": False,
        "success": False,
        "radio_info": {},
        "errors": [],
    }
    
    try:
        import pyrf24
        result["attempted"] = True
        
        radio = pyrf24.RF24(25, 0)
        if radio.begin():
            result["success"] = True
            radio.setPALevel(pyrf24.RF24_PA_LOW)
            radio.setDataRate(pyrf24.RF24_1MBPS)
            radio.setCRCLength(pyrf24.RF24_CRC_16)
            radio.stopListening()
            
            result["radio_info"] = {
                "channel": radio.getChannel(),
                "pa_level": radio.getPALevel(),
                "data_rate": radio.getDataRate(),
                "crc_length": radio.getCRCLength(),
                "is_p_variant": radio.isPVariant(),
            }
            
            if read_only:
                rpd = radio.testRPD()
                result["radio_info"]["test_rpd"] = bool(rpd)
            
            radio.powerDown()
        else:
            result["errors"].append("radio.begin() returned False - check wiring")
    
    except Exception as e:
        result["errors"].append(f"Hardware init failed: {e}")
    
    return result


def run_full_diagnostic(read_only: bool = True) -> Dict[str, Any]:
    """Run complete diagnostic suite."""
    print("=" * 60)
    print("RF Spectrum Visualizer - pyrf24 Diagnostic Tool")
    print("=" * 60)
    
    results = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": check_python_version(),
        },
        "pyrf24": check_pyrf24_installation(),
        "spi": check_spi_devices(),
        "gpio": check_gpio_access(),
        "hardware_init": attempt_hardware_init(read_only),
    }
    
    print("\n1. Platform Information")
    print(f"   System: {results['platform']['system']} {results['platform']['release']} ({results['platform']['machine']})")
    print(f"   Python: {results['platform']['python']['version'].split()[0]}")
    print(f"   Python OK: {results['platform']['python']['acceptable']}")
    
    print("\n2. pyrf24 Installation")
    p = results["pyrf24"]
    print(f"   Installed: {p['installed']}")
    if p["installed"]:
        print(f"   Version: {p['version']}")
        print(f"   Location: {p['location']}")
        print(f"   Classes found: {[k for k,v in p['classes'].items() if v]}")
        missing_methods = [k for k,v in p['methods'].items() if isinstance(v, bool) and not v]
        if missing_methods:
            print(f"   Missing critical methods: {missing_methods}")
        missing_consts = [k for k,v in p['constants'].items() if not v]
        if missing_consts:
            print(f"   Missing constants: {missing_consts}")
    if p["errors"]:
        for err in p["errors"]:
            print(f"   Error: {err}")
    
    print("\n3. SPI Devices")
    print(f"   Found: {results['spi']['devices'] or 'None'}")
    print(f"   Accessible: {results['spi']['accessible'] or 'None'}")
    for err in results["spi"]["errors"]:
        print(f"   Error: {err}")
    
    print("\n4. GPIO Access")
    print(f"   /dev/gpiomem: {results['gpio']['gpiomem_accessible']}")
    print(f"   /dev/gpiochip0: {results['gpio']['gpiochip_accessible']}")
    
    print("\n5. Hardware Initialization (read-only test)")
    h = results["hardware_init"]
    print(f"   Attempted: {h['attempted']}")
    print(f"   Success: {h['success']}")
    if h["success"]:
        print(f"   Radio info: {h['radio_info']}")
    for err in h["errors"]:
        print(f"   Error: {err}")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    can_run_hardware = (
        results["platform"]["python"]["acceptable"] and
        results["pyrf24"]["installed"] and
        len(results["spi"]["accessible"]) > 0 and
        results["gpio"]["gpiomem_accessible"] and
        results["hardware_init"]["success"]
    )
    
    print(f"Hardware mode available: {can_run_hardware}")
    print(f"Simulation mode available: True (always)")
    
    if not can_run_hardware:
        print("\nTo enable hardware mode:")
        if not results["pyrf24"]["installed"]:
            print("  - Install pyrf24: pip install pyrf24 (or build from source)")
        if not results["spi"]["accessible"]:
            print("  - Enable SPI: sudo raspi-config -> Interface Options -> SPI -> Enable")
            print("  - Install spidev: pip install spidev")
        if not results["gpio"]["gpiomem_accessible"]:
            print("  - Add user to gpio group: sudo usermod -a -G gpio $USER")
        if not results["hardware_init"]["success"]:
            print("  - Check nRF24L01+ wiring (CE=GPIO25, CSN=CE0, SCK=GPIO11, MOSI=GPIO10, MISO=GPIO9)")
            print("  - Ensure 3.3V power supply (NOT 5V)")
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="pyrf24 API diagnostic tool")
    parser.add_argument("--init", action="store_true", help="Attempt hardware initialization")
    parser.add_argument("--read-write", action="store_true", help="Allow write operations during init test")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    
    results = run_full_diagnostic(read_only=not args.read_write)
    
    if args.json:
        import json
        print(json.dumps(results, indent=2, default=str))
    
    sys.exit(0 if results["hardware_init"]["success"] or not args.init else 1)


if __name__ == "__main__":
    main()