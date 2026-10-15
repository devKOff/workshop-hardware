# ESP32 Random-Channel RF Test Generator V4.1 - Architecture Document

## System Overview

The ESP32 Random-Channel RF Test Generator V4.1 is a modular, event-driven embedded firmware system designed to generate bounded, pseudorandom RF test bursts using the nRF24L01+ transceiver. The system emphasizes safety, testability, and maintainability through clean separation of concerns.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
                        APPLICATION LAYER
┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌───────────┐
│   Main      │  │  Button      │  │   Radio     │  │  Logger   │
│   Loop      │◄─│  Handler     │  │  Controller │  │  (Singleton)│
│ (State Mgr) │  │  (Debounce)  │  │  (Burst TX) │  │           │
└──────┬──────┘  └──────┬───────┘  └──────┬──────┘  └─────┬─────┘
       │                │                 │               │
       ▼                ▼                 ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
                      HARDWARE ABSTRACTION LAYER
│  ESP32 Arduino Core  │  RF24 Library  │  GPIO/Serial Drivers  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
                         PHYSICAL HARDWARE
│  ESP32 MCU  │  nRF24L01+ SPI  │  Button  │  Status LED  │  USB  │
└─────────────────────────────────────────────────────────────────┘
```

## Module Descriptions

### 1. Main Loop / State Manager (`src/main.cpp`)

**Responsibilities:**
- Firmware state machine orchestration
- Module initialization and coordination
- Watchdog timing enforcement
- Status LED pattern generation
- Periodic health reporting

**State Machine:**
```
INITIALIZING -> IDLE -> BURST_IN_PROGRESS -> IDLE
                     |                         ^
                     |                         |
                     v                         |
               ERROR_STATE --------------------+
                     ^
                     | (Long press recovery)
                     +--------------------------
```

**State Details:**
| State | Entry Action | Exit Condition | Timeout |
|-------|--------------|----------------|---------|
| INITIALIZING | Init HW, radio, button | Radio ready | 5s |
| IDLE | Wait for button | Button press | 10s (warn) |
| BURST_IN_PROGRESS | Start TX burst | Burst complete | 5s (abort) |
| ERROR_STATE | Log error, power down radio | Long press recovery | None |

### 2. Button Handler (`src/button_handler.cpp`, `include/button_handler.h`)

**Responsibilities:**
- Hardware button debouncing (50ms default)
- Short press vs long press discrimination (1000ms threshold)
- Event queue for main loop consumption
- Non-blocking state machine implementation

**Internal State Machine:**
```
IDLE -> DEBOUNCE_PRESS -> PRESSED -> DEBOUNCE_RELEASE -> IDLE
                                      |                    ^
                                      | (1000ms)           |
                                      v                    |
                              LONG_PRESS_DETECTED ---------+
```

**Events Generated:**
- `SHORT_PRESS`: Button pressed 50ms - 1000ms
- `LONG_PRESS`: Button held >1000ms
- `NONE`: No actionable event

### 3. Radio Controller (`src/radio_controller.cpp`, `include/radio_controller.h`)

**Responsibilities:**
- nRF24L01+ initialization and configuration
- Bounded burst transmission management
- Channel configuration and validation
- Packet construction and transmission
- Hardware error detection and reporting

**Key Constraints (Safety):**
- Maximum **20 packets per burst** (configurable, max 255)
- **RF24_PA_LOW** power setting (-6 dBm)
- **1ms inter-packet delay** minimum
- Automatic **power down** after burst completion
- Channel validation: **0-125 only**

**Transmission Flow:**
```
startBurst(ch, count, delay)
    |
    v
Validate channel (0-125)
    |
    v
Configure RF channel
    |
    v
Power up, flush FIFOs
    |
    v
STATE = TRANSMITTING
    |
    v
update() called from main loop
    |
    +-> Send packet (non-blocking)
    |       |
    |       v
    |   Increment sequence
    |       |
    |       v
    |   Update timestamp
    |       |
    |       v
    |   Check count reached?
    |       |
    |       +-- No -> Wait for inter-packet delay
    |       |
    |       +-- Yes -> Power down, STATE = READY
    |
    v
```

### 4. Packet Protocol (`include/packet_protocol.h`)

**Packet Structure (32 bytes max):**
```cpp
struct TestPacket {
    uint32_t magic;        // 0x45535034 ("ESP4")
    uint8_t  version;      // Protocol version (1)
    uint16_t burst_id;     // Monotonic burst counter
    uint16_t sequence;     // Per-burst sequence (0..N-1)
    uint8_t  channel;      // RF channel (0-125)
    uint32_t frequency_mhz;// Calculated: 2400 + channel
    uint8_t  padding[18];  // 0xAA fill to 32 bytes
}; // Total: 32 bytes
```

**Validation Rules:**
- Magic bytes must equal `0x45535034`
- Version must equal `1`
- Channel must be in range [0, 125]
- Frequency must match `2400 + channel`

### 5. Logger (`src/logger.cpp`, `include/logger.h`)

**Responsibilities:**
- Thread-safe singleton logging
- Configurable log levels (SILENT..VERBOSE)
- Timestamped output with tags
- Structured logging for packets, bursts, state changes

**Log Levels:**
| Level | Value | Use Case |
|-------|-------|----------|
| SILENT | 0 | Disable all output |
| ERROR | 1 | Critical failures only |
| WARN | 2 | Recoverable issues |
| INFO | 3 | Normal operations (default) |
| DEBUG | 4 | Detailed flow tracing |
| VERBOSE | 5 | Packet-level detail |

## Data Flow

### Button Press to RF Burst

```
User Presses Button
        |
        v
ButtonHandler.update() -> Detects SHORT_PRESS/LONG_PRESS
        |
        v
Main Loop: getEvent() returns event
        |
        v
Short Press: radio.generateRandomChannel() -> 0-125
Long Press:  config::RF_CHANNEL_DEFAULT (2)
        |
        v
RadioController.startBurst(channel, 20, 1000)
        |
        v
RadioController.update() called each loop()
        |
        v
For each packet (max 20):
    +- Create TestPacket with burst_id, seq, channel, freq
    +- radio.write() via SPI
    +- Wait 1ms (inter-packet delay)
    +- Repeat
        |
        v
Burst complete -> Radio power down -> STATE = IDLE
```

## Configuration System (`include/config.h`)

Centralized compile-time constants:
- Pin assignments
- Timing parameters (debounce, delays, timeouts)
- RF parameters (PA level, data rate, CRC)
- Protocol constants (pipe address, packet size)
- Channel/frequency mapping

All values are `constexpr` for compile-time optimization.

## Concurrency Model

**Single-threaded, cooperative multitasking:**
- All modules use non-blocking `update()` pattern
- No RTOS tasks, interrupts, or blocking delays
- `yield()` called in main loop for WiFi stack
- Watchdog-friendly: no operation exceeds 5ms

## Memory Management

- **Static allocation only** - no `malloc`/`new` in runtime
- Packet buffers allocated as class members
- String literals in flash (PROGMEM) where possible
- Target: <50KB RAM, <500KB Flash

## Error Handling Strategy

| Layer | Mechanism |
|-------|-----------|
| Radio | Return codes + error enum + state machine |
| Button | State machine ignores glitches |
| Main | State transitions + watchdog timeouts |
| Logger | Graceful degradation (no crash on serial full) |

## Extensibility Points

1. **New button actions**: Add events to `ButtonEvent` enum
2. **New RF protocols**: Extend `RadioController` with virtual methods
3. **Packet formats**: Modify `TestPacket` struct (max 32 bytes)
4. **Logging outputs**: Add `LogSink` interface to `Logger`
5. **State machine**: Add states to `FirmwareState` enum

## Testing Architecture

**Unit Tests (Native/Unity):**
- `test_config.cpp`: Config validation, channel-freq mapping
- `test_button_logic.cpp`: Debounce state machine, press classification
- `test_packet_protocol.cpp`: Serialization, validation, edge cases
- `test_radio_controller.cpp`: State transitions, parameter validation
- `test_main.cpp`: Integration constants, enum values

**Hardware-in-Loop Tests (Manual):**
- Button press -> burst generation
- Channel verification via spectrum analyzer
- Packet capture via second nRF24L01+
- Power consumption measurement

## Build System

**PlatformIO Configuration:**
- Target: `esp32dev` (ESP32 DevKit)
- Framework: Arduino
- Library: `nrf24/RF24@^1.4.9`
- Test Framework: Unity
- Standards: C++17, `-Wall -Wextra -Werror -pedantic`

---

*Architecture Version: 4.1*
*Last Updated: 2026-10-15*