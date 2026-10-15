# Test Plan

## Test Categories

### 1. Configuration Tests (`test_config.cpp`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Default config | Verify default values match constants | All defaults valid |
| Valid radio config | Min/max channels, packets, interval, power, payload | `validateRadioConfig` = true |
| Invalid min > max | channel_min > channel_max | `validateRadioConfig` = false |
| Out of bounds channel | channel_min < 0 or channel_max > 125 | `validateRadioConfig` = false |
| Zero packets | packets_per_burst = 0 | `validateRadioConfig` = false |
| Excessive packets | packets_per_burst > 1000 | `validateRadioConfig` = false |
| Zero interval | packet_interval_ms = 0 | `validateRadioConfig` = false |
| Excessive interval | packet_interval_ms > 10000 | `validateRadioConfig` = false |
| Invalid TX power | tx_power_dbm < -18 or > 0 | `validateRadioConfig` = false |
| Invalid payload | payload_size = 0 or > 32 | `validateRadioConfig` = false |
| Valid button config | debounce_ms in 1-1000 | `validateButtonConfig` = true |
| Invalid button debounce | debounce_ms = 0 or > 1000 | `validateButtonConfig` = false |
| Full app config | Combined radio + button validation | `validateAppConfig` = true/false |
| Mutable config | Modify and retrieve config | Changes persist |

**Commands:**
```bash
platformio test -e esp32dev_test -f test_config
```

---

### 2. Packet Protocol Tests (`test_packet_protocol.cpp`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Packet size | sizeof(TestPacket) ≤ MAX_PAYLOAD_SIZE | Pass (currently FAIL - 37 > 32) |
| Serialize/deserialize | Round-trip preserves all fields | All fields match |
| Invalid magic | Magic ≠ 0x5246 | Deserialize fails |
| Invalid version | Version ≠ 1 | Deserialize fails |
| Truncated buffer | Buffer < sizeof(TestPacket) | Deserialize fails |
| Corrupted CRC | Modify last byte | Deserialize fails |
| CRC consistency | Same data → same CRC | CRC matches |
| Fill payload | Deterministic pattern | Repeatable, varies with seq/burst |
| Boundary values | Max burst_id, seq, channel | Serialize/deserialize works |

**Known Issue:** `TestPacket` is 37 bytes but `MAX_PAYLOAD_SIZE` = 32. Must reduce payload from 24 to 19 bytes or increase max payload (not possible on nRF24L01+).

**Commands:**
```bash
platformio test -e esp32dev_test -f test_packet_protocol
```

---

### 3. Button Logic Tests (`test_button_logic.cpp`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| One press = one event | Press → release → press | 2 callbacks, count=2 |
| Held button | Hold for 10 updates | 1 callback, no repeat |
| Contact bounce | Rapid toggle 5x then press | 1 callback |
| Release & press again | Press, release, wait, press | 2 callbacks |
| Boot-time pressed | Button held at begin() | 0 callbacks |
| Invalid input | Random updates without press | No uncontrolled activity |
| Reset counter | Press, reset, check | Count = 0 |
| isPressed() | Debounced state matches | True when pressed |

**Commands:**
```bash
platformio test -e esp32dev_test -f test_button_logic
```

---

### 4. Radio Controller Tests (`test_radio_controller.cpp`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Mock init success | begin() with no failure | State = IDLE |
| Mock init failure | setFailInit(true) | State = ERROR |
| Channel config | Start burst at min/max/invalid | Valid: IDLE→BURST, Invalid: false |
| Bounded packets | 5 packets, 10ms interval | 5 sent, then IDLE |
| Burst termination | abortBurst() mid-burst | State = IDLE, no more sends |
| Transmit failure | setFailSend(true) | 0 packets sent |
| Recovery to idle | Complete burst, start new | Multiple bursts work |
| No writes after complete | Update after IDLE | Packet count stable |
| No transmit on config fail | Invalid channel range | startBurst = false |
| Safe after error | Init fail, then startBurst | Remains ERROR |
| Channel→frequency | 0→2400, 42→2442, 125→2525 | Correct MHz |
| isValidChannel | In/out of configured range | True/false |

**Commands:**
```bash
platformio test -e esp32dev_test -f test_radio_controller
```

---

### 5. Integration Tests (`test_integration.cpp`)

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Button → Radio burst | Press triggers burst | 1 burst per press |
| Multiple presses | 5 sequential presses | 5 bursts, different channels |
| Radio init failure | Mock fail init, press button | No burst, safe state |
| Error & recovery | Fail send on 2nd burst | 1st/3rd succeed, 2nd fails |
| Config changes | Change channel range | New range enforced |
| Logging | Check callback messages | Init, burst start, complete |
| State machine | Trace UNINIT→IDLE→BURST→IDLE | Correct transitions |
| No infinite loops | Max 1000 updates | Completes < 1000 |
| Packet protocol integration | Full serialize→radio→deserialize | Valid packet |

**Commands:**
```bash
platformio test -e esp32dev_test -f test_integration
```

---

### 6. ESP32 Compile Test

| Check | Command | Expected |
|-------|---------|----------|
| Syntax/Compile | `platformio run -e esp32dev` | Success, no errors |
| Warnings | `platformio run -e esp32dev` | Zero warnings (with -Wall -Wextra) |
| Size | `platformio run -e esp32dev -t size` | < 1MB flash, < 300KB RAM |

---

### 7. Hardware Validation Tests (Manual)

| Test | Procedure | Pass Criteria |
|------|-----------|---------------|
| Power-on | Apply power, open Serial | Boot banner, "Waiting for button" |
| Radio init | Check logs | "Radio initialization successful" |
| Button press | Press once | Burst starts, logs channel/freq |
| Channel change | Press 5x | 5 different channels logged |
| Burst completes | Wait after press | "Burst complete", "Radio idle" |
| LED indication | Observe LED | On during burst, off in idle |
| Visualizer correlation | Pi visualizer running | Same channel shows activity |
| Power stability | Multiple bursts | No brownout/reset |
| Long press | Hold 5s | Single burst only |
| Rapid press | Press 5x quickly | 5 bursts, no overlap |

---

## Test Execution Summary

### Automated (Native)
```bash
# Run all native tests
platformio test -e esp32dev_test

# Run specific test
platformio test -e esp32dev_test -f test_config
platformio test -e esp32dev_test -f test_packet_protocol
platformio test -e esp32dev_test -f test_button_logic
platformio test -e esp32dev_test -f test_radio_controller
platformio test -e esp32dev_test -f test_integration
```

### Automated (ESP32 Target)
```bash
# Compile for ESP32 (no upload)
platformio run -e esp32dev
```

### Manual (Hardware Required)
```bash
# Upload and monitor
platformio run -e esp32dev -t upload
platformio device monitor -e esp32dev
```

---

## Pass/Fail Criteria

| Category | Pass Threshold |
|----------|----------------|
| Config tests | 100% pass |
| Packet protocol | 100% pass (after size fix) |
| Button logic | 100% pass |
| Radio controller | 100% pass |
| Integration | 100% pass |
| ESP32 compile | 0 errors, 0 warnings |
| Hardware tests | All 10 manual tests pass |

---

## Regression Checklist

After any change:
- [ ] All native tests pass
- [ ] ESP32 compile succeeds
- [ ] No new compiler warnings
- [ ] Packet size ≤ 32 bytes
- [ ] No unbounded loops added
- [ ] Config validation still works
- [ ] State machine transitions correct

---

## Known Test Gaps

1. **Packet size** - TestPacket exceeds 32 bytes (must fix before hardware test)
2. **No RF emission test** - Requires spectrum analyzer or Pi visualizer
3. **No power measurement** - Requires USB power meter or oscilloscope
4. **No ESD/transient test** - Not in scope
5. **No temperature test** - Not in scope
6. **No long-duration test** - Not in scope