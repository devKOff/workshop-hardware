#!/usr/bin/env python3
"""
Environment check script for ESP32 Random-Channel RF Test Generator V4
"""
import sys
import subprocess
import platform
import shutil

def run_cmd(cmd, capture=True):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)

def check_platformio():
    ok, out, err = run_cmd("platformio --version")
    if ok:
        print(f"[OK] PlatformIO: {out}")
        return True
    else:
        print(f"[FAIL] PlatformIO not found: {err}")
        return False

def check_python():
    version = sys.version.split()[0]
    print(f"[OK] Python: {version}")
    return True

def check_git():
    ok, out, err = run_cmd("git --version")
    if ok:
        print(f"[OK] Git: {out}")
        return True
    else:
        print(f"[WARN] Git not found: {err}")
        return False

def check_platformio_esp32():
    ok, out, err = run_cmd("platformio platform show espressif32")
    if ok and "espressif32" in out:
        print(f"[OK] ESP32 platform installed")
        return True
    else:
        print(f"[FAIL] ESP32 platform not installed")
        return False

def check_rf24_lib():
    ok, out, err = run_cmd("platformio lib list --builtin")
    if ok and "RF24" in out:
        print(f"[OK] RF24 library available")
        return True
    else:
        print(f"[WARN] RF24 library not in cache (will install on build)")
        return True

def check_project_structure():
    import os
    required = [
        "platformio.ini",
        "include/config.h",
        "include/packet_protocol.h",
        "include/button_handler.h",
        "include/radio_controller.h",
        "include/logger.h",
        "src/main.cpp",
        "src/config.cpp",
        "src/packet_protocol.cpp",
        "src/button_handler.cpp",
        "src/radio_controller.cpp",
        "src/logger.cpp",
        "test/test_config.cpp",
        "test/test_packet_protocol.cpp",
        "test/test_button_logic.cpp",
        "test/test_radio_controller.cpp",
        "test/test_integration.cpp",
    ]
    missing = []
    for f in required:
        if not os.path.exists(f):
            missing.append(f)
    if missing:
        print(f"[FAIL] Missing files:")
        for f in missing:
            print(f"   - {f}")
        return False
    else:
        print(f"[OK] All project files present")
        return True

def main():
    print("=" * 60)
    print("ESP32 Random-Channel RF Test Generator V4 - Environment Check")
    print("=" * 60)
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Arch: {platform.machine()}")
    print()

    checks = [
        ("Python", check_python),
        ("Git", check_git),
        ("PlatformIO", check_platformio),
        ("ESP32 Platform", check_platformio_esp32),
        ("RF24 Library", check_rf24_lib),
        ("Project Structure", check_project_structure),
    ]

    results = []
    for name, fn in checks:
        try:
            results.append((name, fn()))
        except Exception as e:
            print(f"[FAIL] {name} check failed with exception: {e}")
            results.append((name, False))

    print()
    print("=" * 60)
    print("Summary:")
    all_ok = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n[OK] All checks passed. Ready to build.")
        return 0
    else:
        print("\n[FAIL] Some checks failed. Fix before building.")
        return 1

if __name__ == "__main__":
    sys.exit(main())