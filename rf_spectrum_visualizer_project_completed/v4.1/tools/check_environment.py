#!/usr/bin/env python3
"""
Environment verification script for ESP32 RF Test Generator V4.1
Checks PlatformIO, Python, and required dependencies.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_cmd(cmd, capture=True):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def check_platformio():
    print("Checking PlatformIO...")
    ok, out, err = run_cmd("pio --version")
    if ok:
        print(f"  ✓ PlatformIO: {out}")
        return True
    else:
        print(f"  ✗ PlatformIO not found: {err}")
        return False


def check_python():
    print("Checking Python...")
    version = sys.version.split()[0]
    print(f"  ✓ Python: {version}")
    return True


def check_git():
    print("Checking Git...")
    ok, out, err = run_cmd("git --version")
    if ok:
        print(f"  ✓ Git: {out}")
        return True
    else:
        print(f"  ✗ Git not found")
        return False


def check_project_structure():
    print("Checking project structure...")
    required = [
        "platformio.ini",
        "src/main.cpp",
        "include/config.h",
        "include/packet_protocol.h",
        "include/button_handler.h",
        "include/radio_controller.h",
        "include/logger.h",
        "test/test_config.cpp",
        "test/test_button_logic.cpp",
        "test/test_packet_protocol.cpp",
        "test/test_radio_controller.cpp",
        "test/test_main.cpp",
    ]

    base = Path(__file__).parent.parent
    all_ok = True
    for f in required:
        path = base / f
        if path.exists():
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f} (MISSING)")
            all_ok = False
    return all_ok


def check_platformio_config():
    print("Checking platformio.ini...")
    base = Path(__file__).parent.parent
    ini_path = base / "platformio.ini"
    if not ini_path.exists():
        print("  ✗ platformio.ini not found")
        return False

    content = ini_path.read_text()
    checks = [
        ("env:esp32dev", "ESP32 environment"),
        ("espressif32", "Platform"),
        ("RF24", "RF24 library"),
        ("unity", "Unity test framework"),
        ("-Werror", "Strict warnings"),
    ]

    all_ok = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✓ {desc}")
        else:
            print(f"  ✗ {desc} (missing '{keyword}')")
            all_ok = False
    return all_ok


def main():
    print("=" * 60)
    print("ESP32 RF Test Generator V4.1 - Environment Check")
    print("=" * 60)

    checks = [
        check_python,
        check_git,
        check_platformio,
        check_project_structure,
        check_platformio_config,
    ]

    results = []
    for check in checks:
        results.append(check())
        print()

    print("=" * 60)
    if all(results):
        print("✓ All checks passed!")
        return 0
    else:
        print("✗ Some checks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())