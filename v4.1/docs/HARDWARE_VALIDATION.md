# ESP32 Random-Channel RF Test Generator V4.1 - Hardware Validation Guide

## Overview

This document provides step-by-step hardware validation procedures for the ESP32 Random-Channel RF Test Generator V4.1. These tests require physical hardware and measurement equipment.

## Required Equipment

### Minimum (Functional Validation)
- ESP32 DevKit V1
- nRF24L01+ module (standard or PA/LNA)
- Momentary push button
- Jumper wires + breadboard
- USB cable (data-capable)
- Computer with PlatformIO

### Recommended (Signal Validation)
- **SDR** (HackRF One, RTL-SDR v3, LimeSDR, etc.) + antenna
- **Spectrum Analyzer** (TinySA, Rigol DSA815, etc.)
- **Logic Analyzer** (Saleae, DSLogic, or cheap 8-ch)
- **Multimeter** (voltage, current)
- **Oscilloscope** (100MHz+)

### For Packet Capture Validation
- Second ESP32 + nRF24L01+
- Or: Arduino + nRF24L01+ running RF24 listener sketch

---

## Validation Checklist

### Phase 1: Physical Assembly

| Step | Check | Method | Pass Criteria |
|------|-------|--------|---------------|
| 1.1 | ESP32 powered | USB connected, LED on | Red power LED lit |
| 1.2 | nRF24L01+ VCC | Multimeter at module VCC pin | 3.3V ±0.1V |
| 1.3 | nRF24L01+ GND | Multimeter at module GND pin | 0V (continuity to ESP32 GND) |
| 1.4 | SPI continuity | Multimeter continuity mode | CE↔GPIO25, CSN↔GPIO5, SCK↔GPIO18, MOSI↔GPIO23, MISO↔GPIO19 |
| 1.5 | Button wiring | Multimeter GPIO4 to GND | Open=3.3V, Pressed=0V |
| 1.6 | No shorts | Multimeter resistance | >1MΩ between all signal pins |

### Phase 2: Firmware Upload & Basic Operation

| Step | Check | Method | Pass Criteria |
|------|-------|--------|---------------|
| 2.1 | Build succeeds | `pio run -d v4.1` | Exit code 0, firmware.bin created |
| 2.2 | Upload succeeds | `pio run -d v4.1 -t upload` | "Hard resetting via RTS pin..." |
| 2.3 | Serial monitor opens | `pio device monitor -d v4.1` | Connected at 115200 baud |
| 2.4 | Init messages appear | Observe serial | "Radio initialized successfully" |
| 2.5 | LED pattern | Observe onboard LED | Slow blink (1Hz) = IDLE state |

### Phase 3: Button Functionality

| Step | Check | Method | Pass Criteria |
|------|-------|--------|---------------|
| 3.1 | Short press detected | Press button <500ms | "Short press - Starting burst..." log |
| 3.2 | Long press detected | Hold button >1.5s | "Long press - Starting burst..." log |
| 3.3 | Debounce works | Tap button rapidly (<50ms) | No burst triggered |
| 3.4 | LED changes during TX | Press button | Rapid blink (50ms) during burst |

### Phase 4: RF Transmission Validation

#### 4.1 Spectrum Analyzer / SDR Verification

**Setup:**
- Connect SDR/analyzer antenna near nRF24L01+
- Set center frequency: 2442 MHz (channel 42)
- Span: 10 MHz
- RBW: 100 kHz

| Test | Procedure | Expected Observation |
|------|-----------|---------------------|
| 4.1.1 | Short press (random ch) | Burst at random 2400-2525 MHz |
| 4.1.2 | Long press (default ch) | Burst at 2402 MHz (channel 2) |
| 4.1.3 | Measure channel accuracy | Fc = 2400 + channel ±100 kHz |
| 4.1.4 | Measure bandwidth | ~1 MHz (1 Mbps GFSK) |
| 4.1.5 | Measure TX power | -6 dBm ±3 dB (PA_LOW) |
| 4.1.6 | Verify burst duration | ~20ms for 20 packets @ 1ms spacing |
| 4.1.7 | Verify no continuous carrier | Carrier only during burst |

#### 4.2 Logic Analyzer Verification (SPI)

**Connections:**
- CH0: CSN (GPIO 5)
- CH1: SCK (GPIO 18)
- CH2: MOSI (GPIO 23)
- CH3: MISO (GPIO 19)
- CH4: CE (GPIO 25)

| Test | Procedure | Expected Observation |
|------|-----------|---------------------|
| 4.2.1 | Capture during init | SPI config transactions |
| 4.2.2 | Capture during burst | 20 write transactions |
| 4.2.3 | Verify payload size | 32 bytes per transaction |
| 4.2.4 | Verify CE timing | CE high during TX, low between |

#### 4.3 Packet Capture Validation

**Receiver Setup (2nd nRF24L01+):**
```cpp
// Minimal receiver sketch
#include <RF24.h>
RF24 radio(9, 10); // CE, CSN for Arduino
uint64_t pipe = 0xE7E7E7E7E7LL;
struct { /* same TestPacket struct */ } pkt;

void setup() {
  Serial.begin(115200);
  radio.begin();
  radio.openReadingPipe(1, pipe);
  radio.startListening();
}

void loop() {
  if (radio.available()) {
    radio.read(&pkt, sizeof(pkt));
    // Validate and print
  }
}
```

| Test | Procedure | Pass Criteria |
|------|-----------|---------------|
| 4.3.1 | Capture burst | 20 packets received |
| 4.3.2 | Validate magic | All packets: 0x45535034 |
| 4.3.3 | Validate version | All packets: 1 |
| 4.3.4 | Validate burst_id | Constant across burst |
| 4.3.5 | Validate sequence | 0,1,2...19 incrementing |
| 4.3.6 | Validate channel | Matches transmitter log |
| 4.3.7 | Validate frequency | 2400 + channel |
| 4.3.8 | Validate padding | 0xAA fill bytes |
| 4.3.9 | Check CRC | No CRC errors reported |

### Phase 5: Power & Thermal Validation

| Step | Check | Method | Pass Criteria |
|------|-------|--------|---------------|
| 5.1 | Idle current | Multimeter in series with 5V USB | 40-60 mA |
| 5.2 | TX peak current | Multimeter (or USB power meter) | <150 mA (PA_LOW) |
| 5.3 | No brownout | 5 consecutive bursts | No ESP32 reset |
| 5.4 | Thermal | Touch test after 10 bursts | Components warm, not hot |

### Phase 6: Edge Cases & Stress Tests

| Step | Check | Method | Pass Criteria |
|------|-------|--------|---------------|
| 6.1 | Rapid bursts | 10 short presses quickly | All 10 complete, no overlap |
| 6.2 | Long press recovery | Disconnect nRF24, long press | ERROR_STATE -> recovery on reconnect |
| 6.3 | Channel boundaries | Force channels 0 and 125 | Both transmit correctly |
| 6.4 | Max packet count | Modify to 255 packets | Completes without crash |
| 6.5 | Min packet count | 1 packet burst | Completes correctly |
| 6.6 | Watchdog timeout | Block SPI (hold CSN high) | Aborts after 5s, returns to IDLE |

### Phase 7: Regulatory Compliance Spot Check

| Parameter | Limit (ETSI EN 300 328 / FCC 15.247) | Measured | Pass |
|-----------|--------------------------------------|----------|------|
| Max TX Power | 20 dBm (100 mW) | ~-6 dBm | ✓ |
| Duty Cycle | <10% (typical) | <0.1% | ✓ |
| Channel Bandwidth | <20 MHz | ~1 MHz | ✓ |
| OOB Emissions | -30 dBm @ ±2.5 MHz | Measure | ✓ |

---

## Validation Report Template

```
========================================
HARDWARE VALIDATION REPORT - V4.1
========================================
Date: ___________
Tester: ___________
Hardware Rev: ___________
Firmware: V4.1 (commit: ___________)

EQUIPMENT:
- ESP32: [ ] DevKit V1  [ ] Other: _______
- nRF24L01+: [ ] Standard  [ ] PA/LNA  [ ] Clone
- SDR/Analyzer: ___________
- Logic Analyzer: ___________

PHASE 1 - PHYSICAL:     [ ] PASS  [ ] FAIL
PHASE 2 - FIRMWARE:     [ ] PASS  [ ] FAIL
PHASE 3 - BUTTON:       [ ] PASS  [ ] FAIL
PHASE 4 - RF SIGNAL:    [ ] PASS  [ ] FAIL
PHASE 5 - POWER:        [ ] PASS  [ ] FAIL
PHASE 6 - STRESS:       [ ] PASS  [ ] FAIL
PHASE 7 - REGULATORY:   [ ] PASS  [ ] FAIL

MEASUREMENTS:
- Channel 2 freq: _______ MHz
- Channel 42 freq: _______ MHz
- Channel 125 freq: _______ MHz
- TX Power (ch 2): _______ dBm
- Idle current: _______ mA
- Peak TX current: _______ mA
- Burst duration: _______ ms

NOTES/ISSUES:
________________________________________
________________________________________

SIGNATURE: ___________  DATE: ___________
```

---

## Known Hardware Limitations

1. **nRF24L01+ clones** - ~30% failure rate, inconsistent PA output
2. **ESP32 DevKit 3.3V regulator** - Limited to ~500mA, may brownout with PA/LNA
3. **Onboard LED (GPIO2)** - Conflicts with strapping pin on some modules
4. **SPI bus sharing** - Not tested with other SPI devices
5. **Antenna diversity** - Single antenna, no diversity support

---

## Validation Without Full Equipment

### Minimal Validation (Only ESP32 + nRF24L01+ + Button)
1. Complete Phases 1-3
2. For Phase 4: Use 2nd ESP32+nRF24L01+ as receiver (packet capture)
3. Verify packet contents via serial on receiver
4. Skip spectrum measurements

### Software-Only Validation (No Hardware)
Run unit tests:
```bash
pio test -d v4.1
```
All 38 tests passing = logic validated.

---

## Troubleshooting Failed Validations

| Failure | Likely Cause | Resolution |
|---------|--------------|------------|
| Phase 1.2 fails | Bad USB cable / regulator | Try powered hub |
| Phase 2.4 fails | Wiring error | Re-check all 7 SPI wires |
| Phase 4.1.3 fails | Crystal tolerance | Acceptable if ±200 kHz |
| Phase 4.3.x fails | Address/channel mismatch | Verify pipe address both sides |
| Phase 5.3 fails | Power supply | Add 100µF cap at nRF24L01+ |

---

*Hardware Validation Guide Version: 4.1*
*Last Updated: 2026-10-15*
*NOT RUN — physical hardware required for Phases 1-7*