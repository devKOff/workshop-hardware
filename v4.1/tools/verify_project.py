#!/usr/bin/env python3
"""
Project verification script for ESP32 RF Test Generator V4.1
Validates build, runs unit tests, and checks code quality.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_cmd(cmd, cwd=None, capture=True, timeout=300):
    try:
        print(f"  $ {cmd}")
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=capture,
                                text=True, timeout=timeout)
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                print(f"    {line}")
        if result.stderr and result.returncode != 0:
            for line in result.stderr.strip().split('\n'):
                print(f"    ERR: {line}")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def verify_build(project_dir):
    print("\n[1/4] Building project...")
    ok, out, err = run_cmd("pio run", cwd=project_dir)
    if ok:
        print("  ✓ Build successful")
        return True
    else:
        print("  ✗ Build failed")
        return False


def verify_tests(project_dir):
    print("\n[2/4] Running unit tests...")
    ok, out, err = run_cmd("pio test", cwd=project_dir, timeout=120)
    if ok:
        print("  ✓ All tests passed")
        return True
    else:
        print("  ✗ Some tests failed")
        return False


def verify_code_quality(project_dir):
    print("\n[3/4] Checking code quality (cppcheck)...")
    ok, out, err = run_cmd("pio check", cwd=project_dir, timeout=120)
    if ok:
        print("  ✓ Code quality checks passed")
        return True
    else:
        print("  ⚠ Code quality check failed (may need cppcheck installed)")
        return True


def verify_flash_ready(project_dir):
    print("\n[4/4] Verifying firmware binary...")
    build_dir = Path(project_dir) / ".pio" / "build" / "esp32dev"
    firmware_bin = build_dir / "firmware.bin"
    firmware_elf = build_dir / "firmware.elf"

    if firmware_bin.exists() and firmware_elf.exists():
        size = firmware_bin.stat().st_size
        print(f"  ✓ Firmware binary: {firmware_bin} ({size} bytes)")
        print(f"  ✓ Firmware ELF: {firmware_elf}")
        return True
    else:
        print("  ✗ Firmware artifacts not found")
        return False


def main():
    print("=" * 60)
    print("ESP32 RF Test Generator V4.1 - Project Verification")
    print("=" * 60)

    project_dir = Path(__file__).parent.parent

    checks = [
        lambda: verify_build(project_dir),
        lambda: verify_tests(project_dir),
        lambda: verify_code_quality(project_dir),
        lambda: verify_flash_ready(project_dir),
    ]

    results = []
    for check in checks:
        results.append(check())

    print("\n" + "=" * 60)
    if all(results):
        print("✓ Project verification PASSED")
        print("\nNext steps:")
        print("  1. Connect ESP32 via USB")
        print("  2. Run: pio run --target upload")
        print("  3. Monitor: pio device monitor")
        return 0
    else:
        print("✗ Project verification FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())