#!/usr/bin/env python3
"""
check_hardware.py — Verify the INA219 hardware on the Raspberry Pi.

Checks:
  * I²C bus is available (`i2cdetect -y 1`)
  * The INA219 responds at the configured I²C address
  * A sample reading can be obtained

Run on the Pi (power and wiring connected first):
    python scripts/check_hardware.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Allow running this script directly: python scripts/check_hardware.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Config, load_config
from app.hardware.ina219_sensor import INA219Sensor, INA219SensorError


def run_i2cdetect() -> str:
    try:
        result = subprocess.run(
            ["i2cdetect", "-y", "1"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except FileNotFoundError:
        return "i2cdetect not found — install i2c-tools and enable I²C."
    except subprocess.CalledProcessError as exc:
        return f"i2cdetect failed: {exc.stderr.strip()}"


def main() -> int:
    print("Solar Panel Monitor — hardware check")
    print("=" * 45)

    config = Config.from_dict(load_config())
    addr = config.ina219_i2c_address

    print(f"\nConfigured I²C address: 0x{addr:02X}")

    print("\n-- i2cdetect -y 1 --")
    print(run_i2cdetect())

    print(f"\n-- INA219 at 0x{addr:02X} --")
    try:
        sensor = INA219Sensor(
            i2c_address=addr,
            shunt_ohms=config.ina219_shunt_ohms,
            max_expected_amps=config.ina219_max_expected_amps,
        )
        if not sensor.connected:
            print(f"  NOT CONNECTED — {sensor.last_error}")
            print("\nTroubleshooting:")
            print("  * Re-run 'sudo i2cdetect -y 1' and confirm the address.")
            print("  * Check wiring per docs/HARDWARE_WIRING.md (POWER OFF first).")
            print("  * Confirm VCC is 3.3 V and GND is common with the Pi.")
            return 1
        reading = sensor.read()
        print(f"  CONNECTED — mode={sensor.mode}")
        print(f"  Bus voltage : {reading.bus_voltage_v} V")
        print(f"  Shunt voltage: {reading.shunt_voltage_mv} mV")
        print(f"  Current     : {reading.current_ma} mA")
        print(f"  Power       : {reading.power_w} W")
        print("\nHardware check PASSED.")
        return 0
    except INA219SensorError as exc:
        print(f"  ERROR — {exc}")
        print("\nTroubleshooting:")
        print("  * Install the ina219 library: pip install ina219")
        print("  * Enable I²C and reboot (see scripts/setup_pi.sh).")
        print("  * Verify the address with 'sudo i2cdetect -y 1'.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
