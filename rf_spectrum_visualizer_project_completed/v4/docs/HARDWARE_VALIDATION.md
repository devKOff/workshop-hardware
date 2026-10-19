# Hardware Validation Checklist

**Status: NOT RUN — Physical hardware required**

This checklist must be completed with actual ESP32 + nRF24L01+ hardware. Software tests cannot validate RF behavior.

---

## Pre-Validation Setup

### Equipment Required
- [ ] ESP32 DevKit (tested: ESP32-WROOM-32 DevKit v1/v4)
- [ ] nRF24L01+ module (regular or PA/LNA version)
- [ ] Push button (tactile, momentary, NO)
- [ ] 3mm/5mm LED + 330Ω resistor (optional)
- [ ] 47µF electrolytic capacitor (6.3V+)
- [ ] 0.1µF ceramic capacitor
- [ ] Breadboard + jumper wires OR perfboard + solder
- [ ] Multimeter
- [ ] USB cable (data + power)
- [ ] Computer with PlatformIO
- [ ] Raspberry Pi 3B+ with RF Spectrum Visualizer (for correlation)

### Power Supply Verification
- [ ] ESP32 powered via USB (5V) → onboard 3.3V regulator
- [ ] **OR** Dedicated AMS1117-3.3 from 5V/VIN → nRF24L01+ VCC
- [ ] Multimeter confirms 3.3V ±0.1V at nRF24L01+ VCC pin
- [ ] Multimeter confirms 0V at nRF24L01+ GND pin
- [ ] Common ground: ESP32 GND = nRF24L01+ GND = Power GND

---

## Wiring Verification

### nRF24L01+ Connections
| Signal | ESP32 Pin | nRF24L01+ Pin | Verified |
|--------|-----------|---------------|----------|
| VCC | 3.3V | 1 | [ ] |
| GND | GND | 2 | [ ] |
| CE | GPIO 25 | 3 | [ ] |
| CSN | GPIO 5 | 4 | [ ] |
| SCK | GPIO 18 | 5 | [ ] |
| MOSI | GPIO 23 | 6 | [ ] |
| MISO | GPIO 19 | 7 | [ ] |

### Capacitors
- [ ] 47µF electrolytic: + to VCC, - to GND at nRF24L01+ pins
- [ ] 0.1µF ceramic: across VCC/GND at nRF24L01+ pins
- [ ] Capacitors as close to pins as possible (<5mm)

### Button
- [ ] One leg → GPIO 4
- [ ] Other leg → GND
- [ ] No external pullup (uses INPUT_PULLUP)

### LED (Optional)
- [ ] Anode → GPIO 2 via 330Ω resistor
- [ ] Cathode → GND

### Visual Inspection
- [ ] No solder bridges on nRF24L01+ (2mm pitch!)
- [ ] No shorts VCC-GND (measure resistance > 1MΩ unpowered)
- [ ] All connections mechanically secure
- [ ] Wires not near antenna area (if PA/LNA version)

---

## Firmware Upload

- [ ] PlatformIO installed and working
- [ ] Project compiles: `platformio run -e esp32dev` → SUCCESS
- [ ] ESP32 connected via USB
- [ ] Correct port selected (auto-detected or manual)
- [ ] Upload: `platformio run -e esp32dev -t upload` → SUCCESS
- [ ] Serial monitor opens: `platformio device monitor -e esp32dev`

---

## Functional Validation

### 1. Boot Sequence
- [ ] Serial shows boot banner:
  ```
  === ESP32 Random-Channel RF Test Generator V4 ===
  Build: <date> <time>
  ```
- [ ] `[INFO] Radio initialization successful`
- [ ] `[INFO] Waiting for button press`
- [ ] No ERROR messages
- [ ] LED (if used) OFF initially

### 2. Button Press Test (Single)
- [ ] Press button firmly, release
- [ ] `[TEST] Burst ID: 1`
- [ ] `[TEST] Selected channel: XX` (0-125)
- [ ] `[TEST] Center frequency: 24XX MHz`
- [ ] `[TEST] Packets attempted: 20` (or configured value)
- [ ] `[TEST] Packets acknowledged: N/A (auto-ack disabled)`
- [ ] `[TEST] Burst complete`
- [ ] `[INFO] Radio returned to idle`
- [ ] `[INFO] Waiting for button press`
- [ ] LED ON during burst, OFF after

### 3. Multiple Press Test
- [ ] Press 5 times with 2-second intervals
- [ ] Each press → new burst with new channel
- [ ] All 5 channels different (probabilistic)
- [ ] All 5 bursts complete cleanly
- [ ] No overlapping bursts

### 4. Long Press Test
- [ ] Hold button for 5 seconds
- [ ] Only ONE burst triggered
- [ ] No repeat bursts while held
- [ ] Release → press again → new burst

### 5. Rapid Press Test
- [ ] Press 5 times as fast as possible
- [ ] Each press → one burst (debouncing works)
- [ ] No missed presses
- [ ] No double-triggers

### 6. Boot-Time Press Test
- [ ] Hold button while powering on / resetting
- [ ] No burst on boot
- [ ] Release → press → burst works normally

---

## RF Validation (Requires Pi Visualizer)

### Setup
- [ ] Raspberry Pi 3B+ running RF Spectrum Visualizer
- [ ] Visualizer scanning 2400-2525 MHz
- [ ] ESP32 and Pi positioned 0.5-1m apart
- [ ] Clear line of sight (or in shielded box)

### Correlation Test
| Press | ESP32 Channel | ESP32 Freq (MHz) | Pi Visualizer Channel | Match? |
|-------|---------------|------------------|----------------------|--------|
| 1 | | | | [ ] |
| 2 | | | | [ ] |
| 3 | | | | [ ] |
| 4 | | | | [ ] |
| 5 | | | | [ ] |

- [ ] At least 3/5 bursts detected by visualizer
- [ ] Detected channels match ESP32 log
- [ ] Note: Visualizer may miss bursts due to scan timing

### Power/Distance Test
- [ ] Move ESP32 to 2m, 5m, 10m from Pi
- [ ] Record max distance with detection
- [ ] Note: -12 dBm default → limited range

---

## Stress Tests

### Extended Operation
- [ ] 50 button presses over 10 minutes
- [ ] No crashes, resets, or hangs
- [ ] Memory stable: `ESP.getFreeHeap()` doesn't decline
- [ ] All bursts complete

### Power Stability
- [ ] Measure 3.3V rail during burst (oscilloscope preferred)
- [ ] No dip below 3.0V
- [ ] No ESP32 brownout reset

### Thermal
- [ ] Touch nRF24L01+ after 20 bursts — should be warm, not hot
- [ ] Touch ESP32 regulator — warm, not burning

---

## Edge Case Tests

### Configuration Boundary Tests
- [ ] Set `channel_min=0, channel_max=0` → only channel 0
- [ ] Set `channel_min=125, channel_max=125` → only channel 125
- [ ] Set `packets_per_burst=1` → single packet bursts
- [ ] Set `packets_per_burst=100` → long bursts
- [ ] Set `tx_power_dbm=0` → max power (verify legal!)
- [ ] Set `tx_power_dbm=-18` → min power

### Error Recovery
- [ ] Disconnect nRF24L01+ power → press button → ERROR state
- [ ] Reconnect power → press button → should reinitialize? (Current: requires restart)

---

## Regulatory Compliance Check

**Before any outdoor or extended testing:**
- [ ] Verify 2.4 GHz ISM band rules for your country
- [ ] Check max EIRP (typically 100mW / 20 dBm for 2.4 GHz)
- [ ] Our default -12 dBm (0.06 mW) is well below limits
- [ ] Channels 0-83 (2400-2483 MHz) generally allowed
- [ ] Channels 84-125 (2484-2525 MHz) may be restricted
- [ ] Do not operate near airports, military, sensitive sites
- [ ] Use shielded test enclosure for extended testing

---

## Test Results Template

```
Date: ___________
Tester: ___________
ESP32 Board: ___________
nRF24L01+ Type: ___________ (regular / PA+LNA)
Power Supply: ___________ (USB / Dedicated LDO)

Boot Test:        PASS / FAIL
Single Press:     PASS / FAIL
Multiple Press:   PASS / FAIL
Long Press:       PASS / FAIL
Rapid Press:      PASS / FAIL
Boot Press:       PASS / FAIL
RF Correlation:   PASS / FAIL / NOT TESTED
Extended Ops:     PASS / FAIL / NOT TESTED
Power Stability:  PASS / FAIL / NOT TESTED
Boundary Config:  PASS / FAIL / NOT TESTED

Issues Found:
1. _________________________________
2. _________________________________
3. _________________________________

Notes:
____________________________________________________________________________
____________________________________________________________________________
```

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Hardware Engineer | | | |
| Firmware Engineer | | | |
| Test Engineer | | | |

---

## Next Steps After Validation

1. Document any hardware-specific issues in `TROUBLESHOOTING.md`
2. Update `config.h` defaults if needed for your board
3. Consider adding:
   - Battery voltage monitoring
   - OTA update capability
   - Multiple button modes (single/double/long press)
   - Channel blacklist for Wi-Fi coexistence
   - RSSI reporting if receiver available