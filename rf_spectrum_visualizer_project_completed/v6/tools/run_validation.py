#!/usr/bin/env python3
"""Validation runner for RF Spectrum Visualizer v6."""

import sys
import subprocess
import time
from pathlib import Path
from typing import List, Tuple


def run_command(cmd: List[str], cwd: Path, timeout: int = 60) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def check_python_version() -> bool:
    """Check Python version is 3.8+."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"[FAIL] Python {version.major}.{version.minor}.{version.micro} (need 3.8+)")
        return False


def check_dependencies() -> bool:
    """Check required dependencies."""
    deps = [
        ("numpy", "import numpy; print(numpy.__version__)"),
        ("matplotlib", "import matplotlib; print(matplotlib.__version__)"),
    ]
    
    all_ok = True
    for name, check_cmd in deps:
        code, out, err = run_command([sys.executable, "-c", check_cmd], Path("."))
        if code == 0:
            print(f"[OK] {name} {out.strip()}")
        else:
            print(f"[FAIL] {name} - {err.strip()}")
            all_ok = False
    
    return all_ok


def run_unit_tests() -> bool:
    """Run pytest unit tests."""
    print("\n--- Running Unit Tests ---")
    code, out, err = run_command(
        [sys.executable, "-m", "pytest", "v6/tests", "-v", "--tb=short"],
        Path("."),
        timeout=120,
    )
    print(out)
    if err:
        print(err, file=sys.stderr)
    return code == 0


def run_cli_tests() -> bool:
    """Run CLI integration tests."""
    print("\n--- Running CLI Tests ---")
    
    tests = [
        (["python", "-m", "v6.cli_scan", "help"], "Help command"),
        (["python", "-m", "v6.cli_scan", "simulate", "--scenario", "quiet"], "Quiet simulation"),
        (["python", "-m", "v6.cli_scan", "simulate", "--scenario", "channel_122_high"], "Channel 122 high"),
        (["python", "-m", "v6.cli_scan", "block", "122", "--reason", "Test"], "Block channel 122"),
        (["python", "-m", "v6.cli_scan", "blocklist"], "Show blocklist"),
        (["python", "-m", "v6.cli_scan", "channel", "122"], "Check channel 122"),
        (["python", "-m", "v6.cli_scan", "unblock", "122"], "Unblock channel 122"),
        (["python", "-m", "v6.cli_scan", "blocklist"], "Show blocklist after unblock"),
        (["python", "-m", "v6.cli_scan", "recommend", "--count", "3"], "Recommendations"),
        (["python", "-m", "v6.cli_scan", "export", "--format", "json"], "Export JSON"),
        (["python", "-m", "v6.cli_scan", "export", "--format", "csv"], "Export CSV"),
        (["python", "-m", "v6.cli_scan", "diagnostic"], "Diagnostic"),
    ]
    
    all_passed = True
    for cmd, name in tests:
        print(f"\n  Testing: {name}")
        print(f"  Command: {' '.join(cmd)}")
        code, out, err = run_command(cmd, Path("."), timeout=30)
        if code == 0:
            print(f"  [OK] PASSED")
        else:
            print(f"  [FAIL] FAILED (code {code})")
            if out:
                print(f"  stdout: {out[:200]}")
            if err:
                print(f"  stderr: {err[:200]}")
            all_passed = False
    
    return all_passed


def test_persistence() -> bool:
    """Test blocklist persistence across restarts."""
    print("\n--- Testing Persistence ---")
    
    blocklist_file = Path("v6/blocklist.json")
    if blocklist_file.exists():
        blocklist_file.unlink()
    
    # Block channel 122
    code, out, err = run_command(
        [sys.executable, "-m", "v6.cli_scan", "block", "122", "--reason", "Persistence test"],
        Path("."),
    )
    if code != 0:
        print("  [FAIL] Block failed")
        return False
    
    # Check blocklist file exists
    if not blocklist_file.exists():
        print("  [FAIL] Blocklist file not created")
        return False
    
    # Verify content
    import json
    with open(blocklist_file) as f:
        data = json.load(f)
    if not any(e["channel"] == 122 for e in data):
        print("  [FAIL] Channel 122 not in blocklist")
        return False
    
    print("  [OK] Blocklist persisted to JSON")
    
    # Simulate restart by running new process
    code, out, err = run_command(
        [sys.executable, "-m", "v6.cli_scan", "channel", "122"],
        Path("."),
    )
    if code != 0 or "BLOCKED" not in out:
        print("  [FAIL] Block not persisted across process boundary")
        return False
    
    print("  ✓ Block persists across process restart")
    
    # Unblock
    code, out, err = run_command(
        [sys.executable, "-m", "v6.cli_scan", "unblock", "122"],
        Path("."),
    )
    if code != 0:
        print("  ✗ Unblock failed")
        return False
    
    # Verify unblocked
    code, out, err = run_command(
        [sys.executable, "-m", "v6.cli_scan", "channel", "122"],
        Path("."),
    )
    if "NOT blocked" not in out:
        print("  ✗ Unblock not persisted")
        return False
    
    print("  ✓ Unblock persists across process restart")
    return True


def test_simulation_determinism() -> bool:
    """Test simulation produces deterministic results with same seed."""
    print("\n--- Testing Simulation Determinism ---")
    
    # Run same scenario twice with same seed
    cmd = [
        sys.executable, "-m", "v6.cli_scan", "simulate",
        "--scenario", "mixed", "--seed", "42"
    ]
    
    code1, out1, err1 = run_command(cmd, Path("."))
    time.sleep(0.5)
    code2, out2, err2 = run_command(cmd, Path("."))
    
    if code1 != 0 or code2 != 0:
        print("  ✗ Simulation runs failed")
        return False
    
    # Extract activity percentages
    import re
    activities1 = re.findall(r'Activity:\s+([\d.]+)%', out1)
    activities2 = re.findall(r'Activity:\s+([\d.]+)%', out2)
    
    if activities1 == activities2:
        print("  [OK] Simulation is deterministic with same seed")
        return True
    else:
        print("  [FAIL] Simulation NOT deterministic")
        print(f"    Run 1: {activities1[:5]}...")
        print(f"    Run 2: {activities2[:5]}...")
        return False


def test_gui_import() -> bool:
    """Test GUI module imports without display."""
    print("\n--- Testing GUI Import ---")
    code, out, err = run_command(
        [sys.executable, "-c", "import v6.app; print('GUI imports OK')"],
        Path("."),
        timeout=30,
    )
    if code == 0:
        print("  [OK] GUI imports successfully")
        return True
    else:
        print(f"  [FAIL] GUI import failed: {err}")
        return False


def test_hardware_graceful_failure() -> bool:
    """Test hardware mode fails gracefully without pyrf24."""
    print("\n--- Testing Hardware Graceful Failure ---")
    
    # This should fail gracefully with a clear error message
    code, out, err = run_command(
        [sys.executable, "-m", "v6.cli_scan", "scan", "--backend", "hardware", "--single"],
        Path("."),
        timeout=10,
    )
    
    # Should fail (not crash) with clear message
    if code != 0 and ("pyrf24" in err or "Hardware" in err or "SPI" in err):
        print("  [OK] Hardware mode fails gracefully with clear error")
        return True
    elif code == 0:
        print("  [WARN] Hardware mode succeeded (pyrf24 available)")
        return True
    else:
        print(f"  [FAIL] Unexpected failure: {err}")
        return False


def main() -> int:
    print("=" * 60)
    print("RF Spectrum Visualizer v6 - Validation Suite")
    print("=" * 60)
    
    v6_path = Path("v6")
    if not v6_path.exists():
        print("ERROR: v6 directory not found")
        return 1
    
    results = []
    
    print("\n=== Environment Checks ===")
    results.append(("Python Version", check_python_version()))
    results.append(("Dependencies", check_dependencies()))
    
    print("\n=== Unit Tests ===")
    results.append(("Unit Tests", run_unit_tests()))
    
    print("\n=== CLI Integration Tests ===")
    results.append(("CLI Tests", run_cli_tests()))
    
    print("\n=== Persistence Tests ===")
    results.append(("Persistence", test_persistence()))
    
    print("\n=== Determinism Tests ===")
    results.append(("Determinism", test_simulation_determinism()))
    
    print("\n=== GUI Import Test ===")
    results.append(("GUI Import", test_gui_import()))
    
    print("\n=== Hardware Graceful Failure ===")
    results.append(("Hardware Graceful Failure", test_hardware_graceful_failure()))
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("ALL VALIDATIONS PASSED [OK]")
    else:
        print("SOME VALIDATIONS FAILED [FAIL]")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())