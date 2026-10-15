#!/usr/bin/env python3
"""
Project verification script - runs static checks on the codebase
"""
import os
import re
import subprocess
import sys

def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)

def check_packet_size():
    """Verify TestPacket fits in 32 bytes"""
    header = "include/packet_protocol.h"
    if not os.path.exists(header):
        return False, "packet_protocol.h not found"
    
    with open(header, 'r') as f:
        content = f.read()
    
    # Find TestPacket struct and payload size
    match = re.search(r'uint8_t\s+payload\[(\d+)\]', content)
    if match:
        payload_size = int(match.group(1))
        # Calculate total: magic(2) + version(1) + reserved(1) + burst_id(4) + seq(2) + channel(1) + payload + crc16(2)
        total = 2 + 1 + 1 + 4 + 2 + 1 + payload_size + 2
        if total <= 32:
            return True, f"TestPacket size: {total} bytes (payload={payload_size})"
        else:
            return False, f"TestPacket size: {total} bytes > 32 MAX (payload={payload_size})"
    
    return False, "Could not determine payload size"

def check_unbounded_loops():
    """Check for potential infinite loops"""
    issues = []
    for root, dirs, files in os.walk("src"):
        for f in files:
            if f.endswith(('.cpp', '.h')):
                path = os.path.join(root, f)
                with open(path, 'r') as fp:
                    content = fp.read()
                # Check for while(true) without break
                if 'while (true)' in content and 'break' not in content:
                    issues.append(f"{path}: while(true) without break")
                # Check for for(;;) without break
                if 'for (;;)' in content and 'break' not in content:
                    issues.append(f"{path}: for(;;) without break")
    if issues:
        return False, "; ".join(issues)
    return True, "No obvious unbounded loops"

def check_spi_pins():
    """Verify SPI pin configuration matches ESP32 hardware SPI"""
    config_file = "include/config.h"
    if not os.path.exists(config_file):
        return False, "config.h not found"
    
    with open(config_file, 'r') as f:
        content = f.read()
    
    expected = {
        'sck_pin': 18,
        'mosi_pin': 23,
        'miso_pin': 19,
    }
    
    for pin, expected_val in expected.items():
        match = re.search(rf'{pin}\s*=\s*(\d+)', content)
        if match:
            val = int(match.group(1))
            if val != expected_val:
                return False, f"{pin} = {val}, expected {expected_val} (hardware SPI)"
    
    return True, "SPI pins match hardware SPI (SCK=18, MOSI=23, MISO=19)"

def check_rf24_api_usage():
    """Check for common RF24 API mistakes"""
    issues = []
    for root, dirs, files in os.walk("src"):
        for f in files:
            if f.endswith('.cpp'):
                path = os.path.join(root, f)
                with open(path, 'r') as fp:
                    content = fp.read()
                
                # Check for deprecated/incorrect APIs
                if 'radio.write' in content and 'sizeof' not in content:
                    issues.append(f"{path}: radio.write() without sizeof")
                if 'setPALevel' in content and 'RF24_PA_' not in content and 'rf24_pa_dbm_e' not in content:
                    issues.append(f"{path}: setPALevel() may use wrong enum")
    
    if issues:
        return False, "; ".join(issues)
    return True, "RF24 API usage looks correct"

def check_config_validation():
    """Verify config validation is called"""
    main_file = "src/main.cpp"
    if not os.path.exists(main_file):
        return False, "main.cpp not found"
    
    with open(main_file, 'r') as f:
        content = f.read()
    
    if 'validateAppConfig' in content:
        return True, "Config validation called in main.cpp"
    return False, "Config validation NOT called in main.cpp"

def check_no_transmit_without_button():
    """Verify no automatic transmission without button press"""
    main_file = "src/main.cpp"
    if not os.path.exists(main_file):
        return False, "main.cpp not found"
    
    with open(main_file, 'r') as f:
        content = f.read()
    
    # Check that startBurst is only called from button callback
    if 'startBurst' in content:
        # Should only be in the burst_requested handler
        idx = content.find('startBurst')
        context = content[max(0, idx-200):idx+200]
        if 'burst_requested' not in context and 'onButtonPress' not in context:
            return False, "startBurst() may be called outside button handler"
    
    return True, "Transmission only triggered by button"

def check_build():
    """Attempt to build the project"""
    ok, out, err = run_cmd("platformio run -e esp32dev")
    if ok:
        return True, "Build successful"
    else:
        return False, f"Build failed: {err[:500]}"

def main():
    print("=" * 60)
    print("ESP32 Random-Channel RF Test Generator V4 - Project Verification")
    print("=" * 60)
    
    checks = [
        ("Packet size <= 32 bytes", check_packet_size),
        ("No unbounded loops", check_unbounded_loops),
        ("SPI pins correct", check_spi_pins),
        ("RF24 API usage", check_rf24_api_usage),
        ("Config validation called", check_config_validation),
        ("No auto-transmit", check_no_transmit_without_button),
        ("Build test", check_build),
    ]
    
    results = []
    for name, fn in checks:
        try:
            ok, msg = fn()
            results.append((name, ok, msg))
            status = "[OK]" if ok else "[FAIL]"
            print(f"{status} {name}: {msg}")
        except Exception as e:
            results.append((name, False, f"Exception: {e}"))
            print(f"[FAIL] {name}: Exception: {e}")
    
    print()
    print("=" * 60)
    all_ok = all(r[1] for r in results)
    if all_ok:
        print("[OK] All verification checks PASSED")
        return 0
    else:
        print("[FAIL] Some verification checks FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())