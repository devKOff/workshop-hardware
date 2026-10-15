# ESP32 Random-Channel RF Test Generator V4.1 - Troubleshooting Guide

## Quick Diagnosis

| Symptom | Section |
|---------|---------|
| Build fails | [Build Issues](#build-issues) |
| Upload fails | [Upload Issues](#upload-issues) |
| "Radio init failed" | [Radio Initialization](#radio-initialization) |
| No serial output | [Serial Communication](#serial-communication) |
| Button not working | [Button Issues](#button-issues) |
| No RF transmission | [RF Transmission](#rf-transmission) |
| Packets not received | [Packet Reception](#packet-reception) |
| Unexpected resets | [Power/Brownout](#powerbrownout-issues) |
| LED patterns wrong | [LED Indicators](#led-indicators) |

---

## Build Issues

### PlatformIO not found
```bash
# Install PlatformIO
pip install platformio
# Or use installer script
python get-platformio.py
```

### Library not found: RF24
```bash
# PlatformIO should auto-install from platformio.ini
# Manual install:
pio lib install "nrf24/RF24@^1.4.9"
```

### Compilation errors with -Werror
```
error: unused variable 'x' [-Werror=unused-variable]
```
**Fix:** Remove unused variables or add `(void)x;` to suppress.

### Multiple definition errors
```
multiple definition of `logger::Logger::instance()'
```
**Cause:** Including `.cpp` files or defining non-inline functions in headers.
**Fix:** Only include `.h` files. Use `inline` for header-defined functions.

### Unity test framework not found
```
fatal error: unity.h: No such file or directory
```
**Fix:** Ensure `test_framework = unity` in platformio.ini and run `pio test` once to fetch.

---

## Upload Issues

### "Failed to connect to ESP32: Timed out waiting for packet header"
**Causes & Fixes:**
1. **Wrong port** - Check `pio device list`, specify `--port /dev/ttyUSB0`
2. **Boot mode** - Hold BOOT button, press/release EN, release BOOT
3. **Driver issues** - Install CP210x or CH340 drivers
4. **Port permissions (Linux)** - `sudo usermod -a -G dialout $USER`

### "A fatal error occurred: Timed out waiting for packet content"
**Fix:** Lower upload speed in platformio.ini: `upload_speed = 115200`

### "Property 'upload_port' not set"
**Fix:** Run `pio device list` to find port, then `pio run -t upload --upload-port /dev/ttyUSB0`

---

## Radio Initialization

### "Radio initialization failed: INIT_FAILED"

**Diagnostic Steps:**
1. **Check wiring** - Verify all 7 connections (VCC, GND, CE, CSN, SCK, MOSI, MISO)
2. **Check power** - Measure 3.3V at nRF24L01+ VCC pin under load
3. **Check SPI pins** - Ensure no other devices on VSPI (GPIO 18, 19, 23, 5)
4. **Try different nRF24L01+ module** - Modules fail frequently
5. **Add capacitor** - 10-100µF electrolytic across VCC/GND at module

**Debug Output:**
```
[ERROR][RADIO] RF24 hardware initialization failed
```
**Check:** `radio.begin()` returns false -> hardware communication failure.

### "Invalid channel" errors
```
[ERROR][MAIN] Invalid channel 200 (valid: 0-125)
```
**Cause:** Channel parameter out of range.
**Fix:** Only use channels 0-125. Default random generator respects this.

---

## Serial Communication

### No serial output at all
1. **Baud rate mismatch** - Ensure 115200 in serial monitor
2. **Wrong port** - Check `pio device list`
3. **USB cable** - Use data cable, not charge-only
4. **Monitor not opened** - Run `pio device monitor` after upload

### Garbled output
1. **Baud rate** - Must be 115200 (config::SERIAL_BAUD)
2. **Line endings** - Set to "Newline" or "Both NL & CR"

### Output stops after "Radio initialized"
**Cause:** Firmware crashed or entered ERROR_STATE.
**Check:** Look for ERROR logs, check LED pattern (double blink = error).

---

## Button Issues

### Button press not detected
1. **Wiring** - Button between GPIO 4 and GND
2. **Pull-up** - Firmware uses `INPUT_PULLUP`, no external resistor needed
3. **Debounce** - Press must exceed 50ms
4. **Active level** - Firmware expects LOW when pressed (connected to GND)

### Multiple presses detected for single press
1. **Mechanical bounce** - Increase `BUTTON_DEBOUNCE_MS` to 100ms
2. **Wiring noise** - Add 0.1µF capacitor across button
3. **Ground loop** - Ensure solid GND connection

### Long press not detected
1. **Hold time** - Must hold >1000ms (config::BUTTON_LONG_PRESS_MS)
2. **Release detection** - Must release cleanly after long press

---

## RF Transmission

### No packets transmitted (radio stuck in TRANSMITTING)
```
[INFO][RADIO] Burst 1 started...
[DEBUG][RADIO] Progress: 5/20 packets
... (stops)
```
**Causes:**
1. **SPI bus conflict** - Another device using VSPI
2. **CSN pin conflict** - GPIO 5 used by other peripheral
3. **Power insufficient** - Brownout during TX
4. **nRF24L01+ faulty** - Try different module

### "Packet send failed" errors
```
[ERROR][RADIO] Packet send failed at sequence 3
```
**Causes:**
1. **FIFO full** - Inter-packet delay too short (increase DEFAULT_INTER_PACKET_DELAY_US)
2. **Channel interference** - WiFi on same channel, try different channel
3. **Power issue** - Add capacitor, check USB power

### Burst completes but packets not received
1. **Receiver not listening** - Ensure RX side configured same pipe/channel
2. **Address mismatch** - Both sides must use 0xE7E7E7E7E7LL
3. **Auto-ACK enabled on RX** - Disable: `radio.setAutoAck(false)`
4. **Distance/obstacles** - Reduce distance, clear line of sight

---

## Packet Reception

### Captured packets have wrong frequency
**Check:** Packet `frequency_mhz` field should equal `2400 + channel`
```
Expected: Channel 42 -> 2442 MHz
Actual:   Channel 42 -> 2442 MHz ✓
```

### Packet validation fails on receiver
**Verify:**
- Magic bytes: 0x45535034 (little-endian: 34 50 53 45)
- Version: 1
- Channel: 0-125
- Frequency matches channel

### Sequence numbers not incrementing
**Check:** Each packet in burst should have sequence 0, 1, 2... 19

---

## Power/Brownout Issues

### ESP32 resets during transmission
**Symptoms:** Serial shows "ets Jul 29 2019 12:21:46" (boot message) mid-burst

**Fixes:**
1. **Better USB cable** - Thick, short, data-rated
2. **Powered hub** - Use powered USB hub
3. **External 3.3V supply** - Feed 3.3V directly to ESP32 3.3V pin (bypass onboard regulator)
4. **Capacitor on nRF24L01+** - 47-100µF electrolytic + 0.1µF ceramic at module VCC/GND
5. **Reduce PA level** - Change `RF_PA_LEVEL` to `RF24_PA_MIN` in config.h

### Current draw measurements
| State | Typical Current |
|-------|-----------------|
| Idle | 40-60 mA |
| Radio init | 80-100 mA |
| TX burst (PA_LOW) | 90-130 mA |
| TX burst (PA_MAX) | 150-250 mA |

---

## LED Indicators

| Pattern | State | Meaning |
|---------|-------|---------|
| Fast blink (100ms) | INITIALIZING | Starting up |
| Slow blink (1s) | IDLE | Ready for button press |
| Rapid blink (50ms) | BURST_IN_PROGRESS | Transmitting packets |
| Double blink (200ms) | ERROR_STATE | Radio error, needs recovery |
| Solid ON | N/A | Firmware crashed |
| Solid OFF | N/A | No power / LED pin issue |

---

## Common Configuration Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| nRF24L01+ VCC to 5V | Module damage, no comms | Use 3.3V ONLY |
| CE/CSN swapped | Init fails | CE=GPIO25, CSN=GPIO5 |
| SPI pins wrong | Init fails | SCK=18, MOSI=23, MISO=19 |
| Button to 3.3V not GND | Never detects press | Button to GND |
| No common GND | Sporadic failures | All GNDs connected |
| Antenna not connected (PA/LNA) | Module damage | Always connect antenna first |

---

## Debugging Tips

### Enable verbose logging
In `main.cpp` setup():
```cpp
Logger::instance().setLevel(LogLevel::VERBOSE);
```

### Monitor free heap
```cpp
Serial.printf("Free heap: %u\n", ESP.getFreeHeap());
```

### Check radio registers
```cpp
radio_.printDetails(); // RF24 library method
```

### Measure actual channel frequency
```cpp
uint32_t freq = config::channelToFrequencyMHz(channel);
Serial.printf("Channel %u = %u MHz\n", channel, freq);
```

### Test with known-good receiver
Use `RF24/examples/GettingStarted` as reference receiver.

---

## Factory Reset / Recovery

If firmware is corrupted:
1. **Erase flash:** `pio run -t erase`
2. **Re-upload:** `pio run -t upload`
3. **Monitor:** `pio device monitor`

---

## Getting Help

1. **Check serial logs** - Most issues logged with [ERROR] tag
2. **Verify wiring** - 90% of issues are wiring
3. **Test components individually** - Button, LED, nRF24L01+ separately
4. **Search existing issues** - PlatformIO, RF24 library GitHub
5. **Minimal reproduction** - Strip to minimal test case

---

*Troubleshooting Guide Version: 4.1*
*Last Updated: 2026-10-15*