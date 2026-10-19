#!/usr/bin/env python3
"""
Test runner script for ESP32 Random-Channel RF Test Generator V4
"""
import subprocess
import sys
import os

def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=cwd)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)

def run_native_tests():
    """Run all native unit tests"""
    print("=" * 60)
    print("Running Native Unit Tests (esp32dev_test environment)")
    print("=" * 60)
    
    ok, out, err = run_cmd("platformio test -e esp32dev_test")
    print(out)
    if err:
        print(err, file=sys.stderr)
    return ok

def run_specific_test(test_filter):
    """Run a specific test"""
    print(f"Running test: {test_filter}")
    ok, out, err = run_cmd(f"platformio test -e esp32dev_test -f {test_filter}")
    print(out)
    if err:
        print(err, file=sys.stderr)
    return ok

def run_build():
    """Build for ESP32 target"""
    print("=" * 60)
    print("Building for ESP32 (esp32dev environment)")
    print("=" * 60)
    
    ok, out, err = run_cmd("platformio run -e esp32dev")
    print(out)
    if err:
        print(err, file=sys.stderr)
    return ok

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run tests for ESP32 RF Test Generator V4")
    parser.add_argument("--native", action="store_true", help="Run native unit tests only")
    parser.add_argument("--build", action="store_true", help="Build for ESP32 only")
    parser.add_argument("--test", type=str, help="Run specific test filter")
    parser.add_argument("--all", action="store_true", help="Run all tests and build")
    args = parser.parse_args()
    
    if not any([args.native, args.build, args.test, args.all]):
        args.all = True
    
    results = []
    
    if args.native or args.all:
        results.append(("Native Tests", run_native_tests()))
    
    if args.test:
        results.append((f"Test: {args.test}", run_specific_test(args.test)))
    
    if args.build or args.all:
        results.append(("ESP32 Build", run_build()))
    
    print()
    print("=" * 60)
    print("Summary:")
    all_passed = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")
        if not ok:
            all_passed = False
    
    if all_passed:
        print("\n[OK] All requested operations PASSED")
        return 0
    else:
        print("\n[FAIL] Some operations FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())