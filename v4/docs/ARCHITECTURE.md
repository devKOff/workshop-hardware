# Architecture Documentation

## Module Responsibilities

### config.h / config.cpp
- **Purpose**: Centralized configuration with validation
- **Responsibilities**:
  - Define all configurable parameters (radio, button, LED, logging)
  - Provide compile-time constants for limits
  - Validate configuration at startup
  - Provide default and mutable configuration access
- **Dependencies**: None (pure C++)

### packet_protocol.h / packet_protocol.cpp
- **Purpose**: Test packet format and serialization
- **Responsibilities**:
  - Define `TestPacket` structure (packed, fixed-size)
  - CRC16 computation (CCITT polynomial 0x1021)
  - Serialize/deserialize to byte buffer
  - Payload pattern generation for identification
  - Boundary and corruption detection
- **Dependencies**: config.h (MAX_PAYLOAD_SIZE, PROTOCOL_VERSION)

### button_handler.h / button_handler.cpp
- **Purpose**: Reliable button debouncing and press detection
- **Responsibilities**:
  - Read physical pin with configurable active-low/high
  - Software debouncing with configurable interval
  - Single-event-per-press semantics (no repeat on hold)
  - Boot-time pressed-button suppression
  - Callback-based event notification
- **Dependencies**: config.h (ButtonConfig), Arduino.h

### radio_controller.h / radio_controller.cpp
- **Purpose**: Radio abstraction with real and mock implementations
- **Responsibilities**:
  - **RadioController**: Real RF24 driver wrapper
    - SPI initialization with custom pins
    - Radio configuration (channel, power, data rate, payload)
    - Bounded burst transmission with interval timing
    - Automatic power-down after burst
    - State tracking and statistics
  - **MockRadioController**: Test double for unit tests
    - Simulates all radio behaviors without hardware
    - Configurable failure injection
    - Deterministic packet counting
- **Dependencies**: config.h, packet_protocol.h, SPI.h, RF24.h (real), Arduino.h

### logger.h / logger.cpp
- **Purpose**: Consistent logging with levels
- **Responsibilities**:
  - Level-based filtering (NONE, ERROR, WARN, INFO, DEBUG, TEST)
  - Formatted output with prefixes
  - Specialized test event logging functions
  - Boot banner with version info
- **Dependencies**: Arduino.h

### main.cpp
- **Purpose**: Firmware entry point and main loop
- **Responsibilities**:
  - Initialize all subsystems
  - Wire button callback to burst initiation
  - Wire radio status callback to logger
  - Main loop: poll button, update radio, handle burst lifecycle
  - LED status indication
  - Random channel selection on each press
- **Dependencies**: All modules

## Firmware State Machine

```
                    ┌─────────────────┐
                    │  UNINITIALIZED  │
                    └────────┬────────┘
                             │ begin()
                             ▼
                    ┌─────────────────┐
         ┌──────────│  INITIALIZING   │──────────┐
         │          └────────┬────────┘          │
         │                   │                   │
    success            failure              (error)
         │                   │                   │
         ▼                   ▼                   │
┌─────────────────┐ ┌─────────────────┐         │
│      IDLE       │ │      ERROR      │─────────┘
└────────┬────────┘ └─────────────────┘
         │ button press
         ▼
┌─────────────────────┐
│ BURST_IN_PROGRESS   │
│  - set channel      │
│  - power up         │
│  - send packets     │
│  - at interval      │
└────────┬────────────┘
         │ packets_sent >= target
         ▼
┌─────────────────┐
│      IDLE       │ (power down, log stats)
└─────────────────┘
```

### State Definitions

| State | Description | Valid Transitions |
|-------|-------------|-------------------|
| UNINITIALIZED | Power-on, before `begin()` | → INITIALIZING |
| INITIALIZING | Radio hardware detection & config | → IDLE (success), → ERROR (failure) |
| IDLE | Radio powered down, waiting for button | → BURST_IN_PROGRESS (button), → UNINITIALIZED (end) |
| BURST_IN_PROGRESS | Transmitting bounded packet sequence | → IDLE (complete/abort), → ERROR (fatal) |
| ERROR | Unrecoverable radio failure | → UNINITIALIZED (end) |

### Transition Rules

1. **UNINITIALIZED → INITIALIZING**: `RadioController::begin()` called
2. **INITIALIZING → IDLE**: RF24 `begin()` succeeds, configuration applied
3. **INITIALIZING → ERROR**: RF24 hardware not responding or allocation fails
4. **IDLE → BURST_IN_PROGRESS**: `startBurst()` called with valid params
5. **BURST_IN_PROGRESS → IDLE**: All packets sent, or `abortBurst()` called
6. **Any → ERROR**: Fatal radio error (not implemented in mock, real driver may detect)
7. **Any → UNINITIALIZED**: `end()` called

## Error Handling Strategy

| Error Type | Detection | Response |
|------------|-----------|----------|
| Config invalid | `validateAppConfig()` at startup | Halt before radio init (infinite loop) |
| Radio not found | `RF24::begin()` returns false | Log ERROR, enter ERROR state |
| Radio allocation fails | `new` returns nullptr | Log ERROR, enter ERROR state |
| Channel out of range | `startBurst()` validation | Return false, stay in IDLE |
| Packet send fails | `RF24::write()` returns false | Log, continue burst (don't abort) |
| Button callback during burst | `g_burst_requested` flag | Ignored until IDLE |

## Test Architecture

### MockRadioController
Implements same interface as RadioController but:
- No hardware dependencies
- Deterministic behavior
- Failure injection (`setFailInit`, `setFailSend`)
- Configurable packet limits (`setMaxPacketsSent`)
- Tracks all state transitions for verification

### Test Categories

1. **Unit Tests** (no hardware):
   - Config validation
   - Packet serialization/CRC
   - Button debouncing logic
   - Mock radio state machine
   - Integration (button → radio)

2. **Hardware Tests** (require ESP32 + nRF24L01+):
   - Radio initialization
   - Channel switching
   - Burst transmission
   - Power measurement
   - Visualizer correlation

## Random Channel Selection

```cpp
uint8_t selectRandomChannel() {
    uint8_t range = channel_max - channel_min + 1;
    uint32_t random_val = random(range);
    return channel_min + static_cast<uint8_t>(random_val);
}
```

- Uses `random()` seeded from `analogRead(entropy_pin) ^ micros()`
- Uniform distribution across configured range
- Testable via MockRadioController channel validation

## Packet Format

```
Offset  Size  Field
────────────────────
0       2     Magic (0x5246 = 'RF')
2       1     Version (1)
3       1     Reserved
4       4     Burst ID (monotonic across boots)
8       2     Sequence (0..packets_per_burst-1)
10      1     Channel (0-125)
11      24    Payload (deterministic pattern)
35      2     CRC16 (CCITT, over bytes 0-34)
Total:  37 bytes (exceeds 32 max payload!)
```

**Note**: Current `TestPacket` is 37 bytes but nRF24L01+ max payload is 32 bytes. This is a known issue — see TEST_PLAN.md for resolution.

## Concurrency Model

Single-threaded, cooperative multitasking in `loop()`:

```cpp
void loop() {
    button.update();      // Non-blocking, ~µs
    radio.update();       // Non-blocking, checks timing

    if (burst_requested) { // Set by button ISR/callback
        handle_burst_start();
    }

    if (radio.idle_after_burst()) {
        log_statistics();
    }
}
```

- No RTOS, no interrupts (except button pin change if configured)
- All timing via `millis()`
- Watchdog-safe: no blocking > 10ms

## Memory Usage Estimate (ESP32)

| Component | RAM | Flash |
|-----------|-----|-------|
| RF24 library | ~2KB | ~40KB |
| Firmware | ~5KB | ~120KB |
| Arduino core | ~20KB | ~400KB |
| **Total** | **~27KB** | **~560KB** |

ESP32 has 520KB SRAM and 4MB flash — well within limits.

## Extensibility Points

1. **Add new radio backends**: Implement `RadioController` interface
2. **Add packet fields**: Extend `TestPacket` (watch payload limit)
3. **Add button types**: Extend `ButtonHandler` (long press, double click)
4. **Add logging outputs**: Extend `logger` (file, network, display)
5. **Add configuration sources**: NVS, WiFi, BLE (modify `getMutableConfig`)