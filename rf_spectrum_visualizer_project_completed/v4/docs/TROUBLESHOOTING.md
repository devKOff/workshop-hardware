# Troubleshooting Guide

## Radio Not Detected

**Symptoms:**
- `[ERROR] RF24 hardware not responding`
- Serial shows UNINITIALIZED or ERROR state
- No burst transmission

**Causes & Fixes:**

| Cause | Check | Fix |
|-------|-------|-----|
| Wrong CE/CSN pins | Verify wiring matches config.h | Correct pins in config.h or rewire |
| SPI pins wrong | SCK=18, MOSI=23, MISO=19 | Use hardware SPI pins only |
| CSN not connected | Floating CSN = radio ignored | Ensure CSN → GPIO 5 solid connection |
| Radio module faulty | Try another nRF24L01+ | Replace module |
| Power issue | See "Unstable Supply" below | Fix power first |
| Clone/fake module | Some clones need longer startup | Add `delay(100)` before `radio.begin()` |

**Debug Steps:**
1. Measure 3.3V at nRF24L01+ VCC pin (multimeter)
2. Check CE/CSN with logic analyzer or LED+resistor
3. Try `RF24` library example `GettingStarted` first
4. Add debug: `Serial.println(radio.getChipModel())` — returns model name or 0

---

## Unstable Supply / Brownout

**Symptoms:**
- ESP32 resets during burst (watchdog or brownout)
- Random garbage on Serial
- Radio works once then fails
- "Guru Meditation Error" on Serial

**Causes & Fixes:**

| Cause | Check | Fix |
|-------|-------|-----|
| ESP32 3.3V regulator overload | Measure 3.3V during TX | Add dedicated LDO (AMS1117-3.3) from 5V |
| Insufficient decoupling | No capacitor at radio | Add 47µF electrolytic + 0.1µF ceramic at VCC/GND |
| Long/thin wires | >10cm Dupont wires | Use shorter, thicker wires; twist VCC/GND |
| USB current limit | Laptop USB port < 500mA | Use powered hub or 5V wall adapter |
| Breadboard contact resistance | Intermittent connections | Solder connections or use perfboard |

**Recommended Power Circuit:**
```
5V (VIN/USB) ────► AMS1117-3.3 ────► 3.3V ────► nRF24L01+ VCC
                              │
                          47µF + 0.1µF
                              │
                             GND ────────────────► nRF24L01+ GND
                                                     ESP32 GND
```

---

## Button Bounce / Multiple Triggers

**Symptoms:**
- Multiple bursts per press
- Burst triggers without pressing
- Erratic behavior

**Causes & Fixes:**

| Cause | Check | Fix |
|-------|-------|-----|
| No debounce | Default 50ms may be too short | Increase `debounce_ms` to 100-200 |
| Floating pin | Button not using pullup | Ensure `INPUT_PULLUP` in config |
| Noisy environment | EMI from radio TX | Add 0.1µF capacitor across button |
| Bad button | Mechanical wear | Replace button |
| Wiring length | Long wires act as antenna | Shorten, add ferrite bead |

**Config Adjustment:**
```cpp
ButtonConfig btn;
btn.debounce_ms = 100;  // Increase from 50
btn.active_low = true;  // Button to GND
```

---

## Compile Errors

### "RF24.h: No such file or directory"
```bash
platformio lib install tmrh20/RF24@^1.4.1
platformio run -e esp32dev -t clean
platformio run -e esp32dev
```

### "SPI.h not found" or SPI errors
```cpp
// In platformio.ini, ensure:
framework = arduino
// SPI is included in Arduino core
```

### "TestPacket size exceeds MAX_PAYLOAD_SIZE"
**Current issue:** `sizeof(TestPacket)` = 37 bytes, max = 32.
**Fix:** Reduce payload array from 24 to 19 bytes in `packet_protocol.h`:
```cpp
uint8_t payload[19];  // Was 24, now 19 = 32 bytes total
```

### "ISO C++ forbids variable length array"
Use `std::array` or fixed-size arrays only.

### Multiple definition errors
Check for duplicate `.cpp` files or multiple `main.cpp`.

---

## Library Incompatibility

**Symptoms:**
- Compile errors in RF24 library
- Runtime crashes in `radio.begin()`
- Wrong API calls

**Tested Versions:**
| Component | Version | Status |
|-----------|---------|--------|
| PlatformIO Core | 6.2.0 | ✅ |
| ESP32 Arduino Core | 2.0.17+ | ✅ |
| RF24 (TMRh20) | 1.4.1+ | ✅ |

**If using different RF24 fork:**
- Check `RF24.h` for `begin()`, `setChannel()`, `write()`, `setPALevel()`
- PA level enum: `RF24_PA_MIN` (-18), `RF24_PA_LOW` (-12), `RF24_PA_HIGH` (-6), `RF24_PA_MAX` (0)
- Data rate enum: `RF24_250KBPS` (0), `RF24_1MBPS` (1), `RF24_2MBPS` (2)

---

## Inconsistent Visualizer Observations

**Symptoms:**
- ESP32 logs channel 42, Pi visualizer shows nothing
- Visualizer shows activity on wrong channel
- Intermittent detection

**Causes & Fixes:**

| Cause | Explanation | Fix |
|-------|-------------|-----|
| Scan interval | Pi scans 1-2 channels/sec | Burst may finish between scans |
| RPD threshold | nRF24L01+ RPD ≈ -64 dBm | Increase TX power to -6 dBm |
| Antenna orientation | Null in radiation pattern | Rotate ESP32 or Pi antenna |
| Distance | Inverse square law | Move closer (<1m for testing) |
| Channel overlap | Wi-Fi on same channel | Test in shielded box or quiet band |
| Auto-ack | No ACK = no retry | Enable auto_ack if receiver present |

**Timing Analysis:**
- Burst: 20 packets × 10ms = 200ms
- Pi sweep: ~125 channels / 2 sec = 62 ch/s
- Probability of catch: ~200ms / (125/62) ≈ 10% per sweep

**Improvements for Detection:**
1. Increase `packets_per_burst` to 50
2. Increase `packet_interval_ms` to 20
3. Set `tx_power_dbm` to -6 (if legal)
4. Use Pi visualizer "single channel monitor" mode

---

## Serial Monitor Issues

| Issue | Fix |
|-------|-----|
| No output | Check baud rate = 115200 |
| Garbled text | Wrong baud, or ESP32 not reset after upload |
| Stops after upload | Press EN (reset) button on ESP32 |
| "Waiting for button" never appears | Radio init failed — check ERROR logs |

---

## Board-Specific Issues

### ESP32 DevKit v1 (Blue LED on GPIO 2)
- GPIO 2 LED is active-LOW
- Firmware sets GPIO 2 LOW at startup (LED off)
- If LED stays on: check `led.active_high` config

### ESP32-C3 / S2 / S3
- Different pinout! Update `config.h`:
```cpp
RadioConfig radio;
radio.sck_pin = 4;   // Example for C3
radio.mosi_pin = 6;
radio.miso_pin = 5;
radio.csn_pin = 7;
radio.ce_pin = 10;
```

### ESP32 with PSRAM
- No changes needed, but monitor heap: `ESP.getFreeHeap()`

---

## Debugging Tips

### Enable Verbose Logging
In `main.cpp`:
```cpp
begin(115200, Level::DEBUG);  // Instead of Level::INFO
```

### Add Radio Register Dump
```cpp
radio.printDetails();  // RF24 method - shows all registers
```

### Measure Actual TX Power
Use RF power meter or spectrum analyzer at antenna.

### Logic Analyzer on SPI
- CSN should go LOW for each transaction
- SCK 4-10 MHz (RF24 default)
- Verify MOSI/MISO data

### Check Channel Frequency
```cpp
// Add to loop for verification:
Serial.printf("Channel %u = %lu MHz\n", ch, 2400 + ch);
```

---

## Getting Help

1. Check `platformio device monitor` output for ERROR/TEST logs
2. Run native tests: `platformio test -e esp32dev_test`
3. Verify wiring against `docs/WIRING.md`
4. Try RF24 library examples independently
5. Search issues: https://github.com/tmrh20/RF24/issues

---

## Emergency Recovery

If ESP32 is bricked or stuck:
1. Hold BOOT button, press EN, release BOOT → download mode
2. `platformio run -e esp32dev -t erase`
3. Re-flash with known-good firmware (Arduino Blink)
4. Then flash this project