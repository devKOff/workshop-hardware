# ESP32 Random-Channel RF Test Generator V4.1

A modular, safety-focused embedded firmware for generating bounded, pseudorandom RF test bursts using the nRF24L01+ transceiver on ESP32.

## Features

- **Bounded RF Transmission**: Maximum 20 packets per burst (configurable), never continuous
- **Pseudorandom Channel Selection**: Channels 0-125 (2400-2525 MHz)
- **Conservative Power**: RF24_PA_LOW (-6 dBm) by default
- **Robust Button Debouncing**: 50ms debounce, short/long press discrimination
- **Structured Packet Protocol**: 32-byte packets with magic, version, burst ID, sequence, channel, frequency
- **State Machine Architecture**: INITIALIZING → IDLE → BURST_IN_PROGRESS → IDLE (with ERROR_STATE)
- **Comprehensive Logging**: Timestamped, leveled logging with structured output
- **Full Unit Test Coverage**: 38 native Unity tests
- **Hardware Safety**: Automatic radio power-down, watchdog timeouts, brownout-resistant

## Hardware Requirements

- ESP32 DevKit V1 (or compatible)
- nRF24L01+ module (standard or PA/LNA)
- Push button (momentary, normally open)
- Jumper wires

## Pin Mapping

| Function | ESP32 GPIO | nRF24L01+ Pin |
|----------|------------|---------------|
| CE | 25 | 3 |
| CSN | 5 | 4 |
| SCK | 18 | 5 |
| MOSI | 23 | 6 |
| MISO | 19 | 7 |
| Button | 4 | - |
| Status LED | 2 (onboard) | - |

**Button**: Connect between GPIO 4 and GND (uses internal pull-up)
**nRF24L01+ VCC**: **MUST** connect to 3.3V (NOT 5V)

## Quick Start

### Prerequisites
- PlatformIO Core (`pip install platformio`)
- ESP32 board connected via USB

### Build & Upload
```bash
cd v4.1
pio run -t upload
```

### Monitor Serial Output
```bash
pio device monitor -b 115200
```

### Run Unit Tests
```bash
pio test
```

### Full Verification
```bash
python tools/verify_project.py
```

## Operation

### LED Indicators
| Pattern | State |
|---------|-------|
| Fast blink (100ms) | Initializing |
| Slow blink (1s) | Idle (ready) |
| Rapid blink (50ms) | Transmitting burst |
| Double blink (200ms) | Error state |

### Button Controls
| Action | Result |
|--------|--------|
| Short press (<1s) | Start burst on random channel (0-125) |
| Long press (>1s) | Start burst on default channel (2 = 2402 MHz) |
| Long press in error | Attempt radio recovery |

### Serial Output Example
```
[00:00:01.234][INFO][MAIN] === ESP32 Random-Channel RF Test Generator V4.1 Starting ===
[00:00:01.235][INFO][MAIN] Pinout: CE=25 CSN=5 BTN=4 LED=2
[00:00:01.235][INFO][MAIN] Channel Range: 0-125 | Default Packets/Burst: 20
[00:00:01.236][INFO][MAIN] Radio initialized successfully
[00:00:01.237][INFO][STATE] Transition: INITIALIZING -> IDLE
[00:00:05.123][INFO][BTN] SHORT_PRESS
[00:00:05.124][INFO][MAIN] Short press - Starting burst on random channel 42 (2442 MHz)
[00:00:05.125][INFO][BURST] Start: ID=1 Ch=42 (2442 MHz) Count=20
[00:00:05.126][DEBUG][RADIO] TX: Burst=1 Seq=0 Ch=42 Freq=2442
...
[00:00:05.146][INFO][BURST] Complete: ID=1 Sent=20/20 (100.0%)
[00:00:05.147][INFO][STATE] Transition: BURST_IN_PROGRESS -> IDLE
```

## Packet Format

```cpp
struct TestPacket {           // 32 bytes total
    uint32_t magic;           // 0x45535034 ("ESP4")
    uint8_t  version;         // 1
    uint16_t burst_id;        // Monotonic burst counter
    uint16_t sequence;        // 0 to packets_per_burst-1
    uint8_t  channel;         // RF channel (0-125)
    uint32_t frequency_mhz;   // 2400 + channel
    uint8_t  padding[18];     // 0xAA fill
};
```

## Configuration

Key parameters in `include/config.h`:

```cpp
constexpr uint8_t DEFAULT_PACKETS_PER_BURST = 20;
constexpr uint16_t DEFAULT_INTER_PACKET_DELAY_US = 1000;
constexpr rf24_pa_dbm_e RF_PA_LEVEL = RF24_PA_LOW;  // -6 dBm
constexpr uint8_t RF_CHANNEL_DEFAULT = 2;            // 2402 MHz
```

## Project Structure

```
v4.1/
├── platformio.ini          # PlatformIO configuration
├── include/                # Header files
│   ├── config.h           # Centralized configuration
│   ├── packet_protocol.h  # Packet structure & validation
│   ├── button_handler.h   # Button debouncing & events
│   ├── radio_controller.h # nRF24L01+ burst management
│   └── logger.h           # Structured logging
├── src/                    # Implementation
│   ├── main.cpp           # State machine & coordination
│   ├── button_handler.cpp
│   ├── radio_controller.cpp
│   └── logger.cpp
├── test/                   # Unity unit tests
│   ├── test_config.cpp
│   ├── test_button_logic.cpp
│   ├── test_packet_protocol.cpp
│   ├── test_radio_controller.cpp
│   └── test_main.cpp
├── tools/                  # Verification scripts
│   ├── check_environment.py
│   └── verify_project.py
└── docs/                   # Documentation
    ├── WIRING.md
    ├── ARCHITECTURE.md
    ├── TEST_PLAN.md
    ├── TROUBLESHOOTING.md
    └── HARDWARE_VALIDATION.md
```

## Safety & Regulatory

- **Not for continuous operation** - Designed for brief test bursts only
- **ISM Band**: 2.4 GHz (2400-2525 MHz)
- **Max Power**: Configured at -6 dBm (PA_LOW)
- **Duty Cycle**: <0.1% (20 packets × 1ms / 10s)
- **FCC 15.247 / ETSI EN 300 328**: Verify compliance for your region
- **Do not operate** near medical, aviation, or safety-critical equipment

## Testing

### Unit Tests (38 tests)
```bash
pio test
```

Test suites:
- `test_config.cpp` - Configuration validation (4 tests)
- `test_button_logic.cpp` - Debouncing logic (7 tests)
- `test_packet_protocol.cpp` - Packet serialization (10 tests)
- `test_radio_controller.cpp` - Radio state machine (8 tests)
- `test_main.cpp` - Integration constants (9 tests)

### Hardware Validation
See `docs/HARDWARE_VALIDATION.md` for complete procedure requiring:
- Spectrum analyzer or SDR
- Logic analyzer (optional)
- Second nRF24L01+ for packet capture

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Radio init failed" | Check wiring, add 47µF cap at nRF24L01+ VCC |
| No serial output | Verify 115200 baud, data-capable USB cable |
| Button not working | Check GPIO 4 to GND, internal pullup enabled |
| Brownout on TX | Better USB cable, powered hub, or external 3.3V |
| Packets not received | Match pipe address (0xE7E7E7E7E7), disable auto-ACK |

Full guide: `docs/TROUBLESHOOTING.md`

## License

MIT License - See LICENSE file for details.

## Version History

- **V4.1** - Complete rewrite: modular architecture, unit tests, safety bounds, documentation
- **V4.0** - Initial version with basic functionality

---

*ESP32 Random-Channel RF Test Generator V4.1*
*Built with PlatformIO, Arduino Framework, RF24 Library, Unity Test Framework*