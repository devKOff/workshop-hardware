# ESP32 Random-Channel RF Test Generator V4.1 - Test Plan

## Test Strategy

This document defines the comprehensive test approach for V4.1, covering unit tests, integration tests, and hardware validation. All automated tests use the Unity framework running natively on the host (not on target).

## Test Categories

### 1. Unit Tests (Automated - Native)

**Target:** 100% coverage of pure logic modules
**Framework:** Unity (via PlatformIO native test)
**Execution:** `pio test -e native` (or `pio test` for on-target)

#### Test Modules

| Test File | Module Under Test | Test Count | Coverage Target |
|-----------|-------------------|------------|-----------------|
| `test_config.cpp` | `config.h` | 4 | 100% |
| `test_button_logic.cpp` | `button_handler.*` | 7 | 95% |
| `test_packet_protocol.cpp` | `packet_protocol.h` | 10 | 100% |
| `test_radio_controller.cpp` | `radio_controller.*` | 8 | 90% |
| `test_main.cpp` | Integration constants | 9 | 80% |

#### test_config.cpp - Configuration Validation

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_channel_to_frequency_mapping` | Verify 2400+channel formula | Ch 0=2400, Ch 42=2442, Ch 125=2525 |
| `test_channel_validation` | Boundary checking 0-125 | Valid: 0,42,125; Invalid: 126,255 |
| `test_config_constants` | Pin assignments, timing values | Match hardware spec |
| `test_rf_config` | PA level, data rate, CRC | PA_LOW, 1Mbps, 2-byte CRC |

#### test_button_logic.cpp - Button Debouncing

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_short_press` | Press 100ms, release | SHORT_PRESS event |
| `test_long_press` | Press 1500ms | LONG_PRESS event |
| `test_press_too_short` | Press 30ms (< debounce) | NONE event |
| `test_multiple_short_presses` | 3 rapid presses | 3 SHORT_PRESS events |
| `test_debounce_rejection` | Glitch during debounce | NONE event |
| `test_is_pressed` | Query during press | TRUE while held |
| `test_press_duration` | Query duration during press | Accurate ms count |

#### test_packet_protocol.cpp - Packet Structure

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_packet_size` | Struct size <= 32 bytes | 32 bytes exactly |
| `test_packet_creation` | All fields populated correctly | Magic, ver, burst, seq, ch, freq |
| `test_packet_validation_valid` | Well-formed packet passes | TRUE |
| `test_packet_validation_invalid_magic` | Wrong magic fails | FALSE |
| `test_packet_validation_invalid_version` | Wrong version fails | FALSE |
| `test_packet_validation_invalid_channel` | Channel >125 fails | FALSE |
| `test_packet_validation_mismatched_frequency` | Freq != 2400+ch fails | FALSE |
| `test_packet_edge_channels` | Ch 0 and 125 valid | Both pass validation |
| `test_packet_sequence_increment` | Sequence increments per packet | 0,1,2...65535 |
| `test_packet_structure_alignment` | Byte layout matches spec | Little-endian fields correct |
| `test_multiple_packets_same_burst` | Burst ID constant, seq varies | Consistent burst_id |

#### test_radio_controller.cpp - Radio Logic

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_constructor_defaults` | Initial state values | UNINITIALIZED, zeros |
| `test_begin_fails_without_hardware` | No HW -> init fails | ERROR_STATE, INIT_FAILED |
| `test_start_burst_before_init` | Burst before begin() | FALSE, INVALID_CHANNEL |
| `test_start_burst_invalid_channel` | Channel 200 rejected | FALSE, INVALID_CHANNEL |
| `test_start_burst_zero_packets` | Zero packets rejected | FALSE |
| `test_start_burst_too_many_packets` | >255 packets rejected | FALSE |
| `test_abort_burst_when_idle` | Abort in READY state | No state change |
| `test_generate_random_channel_range` | 100 samples in 0-125 | All valid |
| `test_state_transitions` | begin/end cycle | UNINIT -> READY -> UNINIT |

#### test_main.cpp - Integration Constants

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_full_packet_workflow` | Create -> validate -> modify | Round-trip valid |
| `test_channel_frequency_consistency` | All 126 channels | All map correctly |
| `test_button_event_enum_values` | Enum ordinal values | NONE=0, SHORT=1, LONG=2 |
| `test_radio_state_enum_values` | Enum ordinal values | 0..4 sequential |
| `test_radio_error_enum_values` | Enum ordinal values | 0..5 sequential |
| `test_logger_levels` | Enum ordinal values | 0..5 sequential |
| `test_firmware_version_string` | Version strings | "V4.1", project name |
| `test_packet_magic_bytes` | Magic constant | 0x45535034 |
| `test_pipe_address` | Pipe address | 0xE7E7E7E7E7LL |

### 2. Build Verification (Automated)

**Command:** `pio run -e esp32dev`
**Success Criteria:**
- Zero compiler warnings (`-Werror`)
- Zero linker errors
- Firmware size < 500KB flash, < 50KB RAM
- Binary artifacts generated (.bin, .elf)

### 3. Static Analysis (Automated)

**Command:** `pio check`
**Tools:** cppcheck (if available)
**Criteria:** No critical defects, style warnings acceptable

### 4. Hardware Validation (Manual - Required)

**Prerequisites:**
- ESP32 DevKit V1
- nRF24L01+ module (standard or PA/LNA)
- Push button
- Spectrum analyzer or SDR (HackRF, RTL-SDR, etc.)
- Second nRF24L01+ + MCU for packet capture (optional)

#### Test Cases

| ID | Test | Procedure | Pass Criteria |
|----|------|-----------|---------------|
| HW-01 | Power-on & Init | Power ESP32, open serial monitor | "Radio initialized successfully" |
| HW-02 | Idle State LED | Observe onboard LED | Slow blink (1Hz) |
| HW-03 | Short Press -> Random Channel | Press button <1s, observe serial | Burst starts, random channel 0-125 |
| HW-04 | Long Press -> Default Channel | Hold button >1s, observe serial | Burst starts, channel 2 (2402 MHz) |
| HW-05 | Burst Packet Count | Count "TX" log lines per burst | Exactly 20 packets (default) |
| HW-06 | Inter-Packet Timing | Measure with logic analyzer/SDR | ~1ms spacing between packets |
| HW-07 | Channel Frequency Accuracy | SDR center frequency measurement | Fc = 2400 + channel MHz ±100kHz |
| HW-08 | PA Level Verification | SDR power measurement | Approximately -6 dBm (PA_LOW) |
| HW-09 | Burst Completion | Observe LED + serial | Rapid blink stops, returns to slow blink |
| HW-10 | Error Recovery | Disconnect nRF24, press button | ERROR_STATE, long press recovers |
| HW-11 | Button Debounce | Tap button rapidly (<50ms) | No burst triggered |
| HW-12 | Multiple Bursts | 5 consecutive short presses | 5 complete bursts, IDs 1-5 |
| HW-13 | Packet Capture | 2nd nRF24L01+ in RX mode | All 20 packets received, valid CRC |
| HW-14 | Packet Content Validation | Decode captured packets | Magic, version, burst_id, seq, ch, freq correct |
| HW-15 | Power Consumption | Measure 3.3V line current | <100mA avg, <150mA peak |

### 5. Regression Tests

Run after any code change:
1. `pio run` - Build must succeed
2. `pio test` - All 38 unit tests must pass
3. `pio check` - Static analysis clean

### 6. CI/CD Integration

**GitHub Actions / GitLab CI Example:**
```yaml
jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup PlatformIO
        uses: platformio/platformio-action@v1
      - name: Build
        run: pio run -d v4.1
      - name: Test
        run: pio test -d v4.1
      - name: Static Analysis
        run: pio check -d v4.1 || true
```

## Test Execution Commands

```bash
# Full verification (build + test + static analysis)
cd v4.1
pio run
pio test
pio check

# Run specific test suite
pio test -f test_config
pio test -f test_button_logic
pio test -f test_packet_protocol
pio test -f test_radio_controller
pio test -f test_main

# Verbose test output
pio test -v

# Native tests only (faster, no hardware)
pio test -e native
```

## Acceptance Criteria for Release

- [ ] All 38 unit tests pass
- [ ] Build completes with zero warnings
- [ ] Static analysis shows no critical defects
- [ ] Hardware tests HW-01 through HW-15 all pass
- [ ] Firmware binary < 500KB flash
- [ ] RAM usage < 50KB
- [ ] No memory leaks (static allocation only)
- [ ] Watchdog-friendly (no blocking >5ms)

## Test Documentation

Each test run should produce:
- Test summary (pass/fail counts)
- Build artifacts (.bin, .elf, .map)
- Test log output
- Code coverage report (if gcov enabled)

---

*Test Plan Version: 4.1*
*Last Updated: 2026-10-15*