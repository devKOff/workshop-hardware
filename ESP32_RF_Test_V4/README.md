# ESP32 Random-Channel RF Test Generator V4

A controlled RF test generator for ESP32 with nRF24L01+ transceiver. Generates a finite burst of test packets on a randomly selected channel when a physical button is pressed.

## Features

- Random channel selection on each button press (configurable range)
- Bounded, finite packet bursts (configurable count and interval)
- Conservative transmit power (-12 dBm default)
- Reliable button debouncing with single-event-per-press semantics
- Complete state machine: INITIALIZING → IDLE → BURST_IN_PROGRESS → IDLE
- Mock radio driver for automated testing without hardware
- Comprehensive test suite (config, packet protocol, button, radio, integration)
- Detailed Serial Monitor logging
- Optional status LED indication

## Hardware Requirements

| Component | Specification |
|-----------|---------------|
| ESP32 DevKit | ESP32-WROOM-32 or compatible |
| nRF24L01+ | 2.4 GHz transceiver module |
| Push button | Normally open, momentary |
| Status LED (optional) | 3mm/5mm LED + 220-470Ω resistor |
| Decoupling capacitor | 10-47 µF electrolytic + 0.1 µF ceramic |
| Power supply | Stable 3.3V @ 200mA+ for nRF24L01+ |

## Wiring

| nRF24L01+ Pin | ESP32 GPIO | Notes |
|--------------|------------|-------|
| VCC | 3.3V | **NOT 5V** - use onboard 3.3V regulator |
| GND | GND | Common ground required |
| CE | GPIO 25 | Chip Enable |
| CSN | GPIO 5 | Chip Select Not |
| SCK | GPIO 18 | SPI Clock |
| MOSI | GPIO 23 | SPI Master Out |
| MISO | GPIO 19 | SPI Master In |
| Button | GPIO 4 | To GND (uses INPUT_PULLUP) |
| LED (optional) | GPIO 2 | With current-limiting resistor |

**Important:** Place the 10-47 µF capacitor directly across the nRF24L01+ VCC/GND pins. The ESP32's 3.3V regulator may not supply sufficient current for the radio during transmission — consider a dedicated 3.3V LDO (e.g., AMS1117-3.3) powered from 5V/VIN.

## Software Prerequisites

- PlatformIO Core 6.x+
- ESP32 Arduino Core (installed automatically by PlatformIO)
- RF24 library by TMRh20 (v1.4.1+)

## Installation

```bash
cd v4
platformio lib install tmrh20/RF24@^1.4.1
```

## Build Commands

```bash
# Build firmware
platformio run -e esp32dev

# Run native unit tests
platformio test -e esp32dev_test

# Upload to ESP32
platformio run -e esp32dev -t upload

# Monitor serial output
platformio device monitor -e esp32dev
```

## Configuration

Edit `include/config.h` or modify `getMutableConfig()` at runtime:

```cpp
RadioConfig radio;
radio.channel_min = 0;        // Minimum channel (0-125)
radio.channel_max = 125;      // Maximum channel (0-125)
radio.packets_per_burst = 20; // Packets per burst (1-1000)
radio.packet_interval_ms = 10; // Interval between packets (1-10000ms)
radio.tx_power_dbm = -12;     // TX power: -18, -12, -6, 0 dBm
radio.payload_size = 32;      // Payload size (1-32 bytes)
radio.auto_ack = false;       // Auto-acknowledge
```

**Regulatory Note:** The nRF24L01+ operates in the 2.4 GHz ISM band (2400-2525 MHz). Channels 0-125 correspond to 2400-2525 MHz. Some channels overlap with Wi-Fi channels 1-13. Verify local regulations before transmitting. In many regions, channels above 83 (2483 MHz) may be restricted.

## Operation

1. Power on the ESP32
2. Open Serial Monitor at 115200 baud
3. Wait for "Waiting for button press"
4. Press and release the button
5. Observe:
   - Random channel selected
   - Burst transmitted
   - Automatic stop after configured packet count
   - Radio returns to idle

Example output:
```
=== ESP32 Random-Channel RF Test Generator V4 ===
Build: Oct 15 2026 10:30:45
[INFO] Radio initialization successful
[INFO] Waiting for button press
[TEST] Burst ID: 1
[TEST] Selected channel: 42
[TEST] Center frequency: 2442 MHz
[TEST] Packets attempted: 20
[TEST] Packets acknowledged: N/A (auto-ack disabled)
[TEST] Burst complete
[INFO] Radio returned to idle
```

## Project Structure

```
v4/
├── platformio.ini          # Build configuration
├ include/
│   ├── config.h           # Configuration structures & validation
│   ├── packet_protocol.h  # Packet format & serialization
│   ├── button_handler.h   # Debounced button handling
│   └── radio_controller.h # Radio abstraction + mock
├ src/
│   ├── main.cpp           # Main firmware
│   ├── config.cpp         # Configuration implementation
│   ├── packet_protocol.cpp # Packet serialization
│   ├── button_handler.cpp # Button debouncing
│   ├── radio_controller.cpp # RF24 driver + mock
│   └── logger.cpp         # Logging implementation
├ test/
│   ├── test_config.cpp
│   ├── test_packet_protocol.cpp
│   ├── test_button_logic.cpp
│   ├── test_radio_controller.cpp
│   └── test_integration.cpp
└── docs/
    ├── WIRING.md
    ├── ARCHITECTURE.md
    ├── TEST_PLAN.md
    ├── TROUBLESHOOTING.md
    └── HARDWARE_VALIDATION.md
```

## Known Limitations

- No hardware test execution in CI (requires physical ESP32 + nRF24L01+)
- Auto-ack disabled by default — no delivery confirmation without receiver
- ESP32 3.3V regulator may brown out during TX — external 3.3V supply recommended
- Channel hopping not implemented — single channel per burst only
- No frequency calibration — uses nominal 2400+N MHz formula

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for:
- Radio not detected (check wiring, power, capacitor)
- Unstable supply (add 47µF capacitor, use dedicated LDO)
- Button bounce (adjust debounce_ms)
- Compile errors (check PlatformIO, library versions)
- Inconsistent visualizer observations (timing, antenna, power)

## License

MIT License — see LICENSE file.

## Test Status

| Test Suite | Status |
|------------|--------|
| Config validation | ✅ Pass |
| Packet protocol | ✅ Pass |
| Button logic | ✅ Pass |
| Radio controller (mock) | ✅ Pass |
| Integration | ✅ Pass |
| ESP32 compile | ✅ Pass |
| Hardware validation | ⏳ Requires hardware |

Run tests: `platformio test -e esp32dev_test`