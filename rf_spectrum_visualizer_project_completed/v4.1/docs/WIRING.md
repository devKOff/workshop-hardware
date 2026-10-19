# ESP32 Random-Channel RF Test Generator V4.1 - Wiring Guide

## Hardware Requirements

- **ESP32 DevKit V1** (or compatible ESP32 board)
- **nRF24L01+ PA/LNA Module** (or standard nRF24L01+)
- **Push Button** (momentary, normally open)
- **Jumper Wires** (female-to-female or male-to-male)
- **Breadboard** (optional, for prototyping)
- **3.3V Power Source** (ESP32 provides this via 3.3V pin)

## Pin Mapping

| nRF24L01+ Pin | ESP32 GPIO | Function | Notes |
|---------------|------------|----------|-------|
| VCC | 3.3V | Power | **DO NOT CONNECT TO 5V** |
| GND | GND | Ground | Common ground required |
| CE | GPIO 25 | Chip Enable | Digital output |
| CSN | GPIO 5 | Chip Select Not | Digital output (SPI CS) |
| SCK | GPIO 18 | SPI Clock | Hardware SPI SCK |
| MOSI | GPIO 23 | SPI MOSI | Hardware SPI MOSI |
| MISO | GPIO 19 | SPI MISO | Hardware SPI MISO |
| IRQ | NC | Interrupt | Not used in this firmware |

| Peripheral | ESP32 GPIO | Function | Notes |
|------------|------------|----------|-------|
| Push Button | GPIO 4 | Input | Connect other side to GND |
| Status LED | GPIO 2 | Output | Onboard LED (blue on most DevKits) |

## Wiring Diagram

```
nRF24L01+                    ESP32 DevKit
┌─────────┐                  ┌──────────────┐
│ 1 VCC   │──────────────────│ 3.3V         │
│ 2 GND   │──────────────────│ GND          │
│ 3 CE    │──────────────────│ GPIO 25      │
│ 4 CSN   │──────────────────│ GPIO 5       │
│ 5 SCK   │──────────────────│ GPIO 18 (SCK)│
│ 6 MOSI  │──────────────────│ GPIO 23 (MOSI)│
│ 7 MISO  │──────────────────│ GPIO 19 (MISO)│
│ 8 IRQ   │                  │ NC           │
└─────────┘                  └──────────────┘

Push Button                ESP32 DevKit
┌─────────┐                ┌──────────────┐
│ Pin 1   │────────────────│ GPIO 4       │
│ Pin 2   │────────────────│ GND          │
└─────────┘                └──────────────┘
(Uses internal pull-up resistor)
```

## Power Considerations

- **nRF24L01+ PA/LNA modules** can draw up to 100-150mA during transmission
- ESP32 3.3V regulator typically supports 500-600mA total
- If experiencing brownouts, add a **10-100µF electrolytic capacitor** across nRF24L01+ VCC/GND
- Consider external 3.3V regulator for PA/LNA versions

## SPI Bus Notes

- Uses **hardware SPI** (VSPI) on ESP32: SCK=18, MOSI=23, MISO=19
- CSN (GPIO 5) is managed by RF24 library
- No other SPI devices should share this bus without proper CS management

## Button Wiring

- **Active LOW** configuration (button connects GPIO to GND when pressed)
- Internal pull-up enabled via `INPUT_PULLUP`
- No external resistor needed
- Debouncing handled in firmware (50ms default)

## Status LED

- **GPIO 2** is the onboard blue LED on most ESP32 DevKits
- Active HIGH (LED on = HIGH)
- Blink patterns indicate firmware state:
  - **Fast blink (100ms)**: Initializing
  - **Slow blink (1s)**: Idle
  - **Rapid blink (50ms)**: Transmitting burst
  - **Double blink (200ms)**: Error state

## Antenna Considerations

- Keep antenna away from metal objects
- For PA/LNA modules, ensure antenna is connected before powering
- Maintain >20cm distance from ESP32 WiFi antenna when possible
- Channel 2 (2402 MHz) is default - avoid WiFi channels 1/6/11 overlap

## Troubleshooting Connections

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "Radio init failed" | Wiring error / power | Check all 7 wires, verify 3.3V |
| "Invalid channel" | Config mismatch | Verify channel 0-125 range |
| No packets received | Antenna / distance | Check antenna, reduce distance |
| Button not responding | Wiring / pullup | Verify GPIO 4 to GND, check pullup |
| Brownout/reset on TX | Power insufficient | Add capacitor, check USB cable |

## Safety & Regulatory Notice

- **This device transmits in the 2.4 GHz ISM band**
- Maximum transmit power configured at **RF24_PA_LOW** (-6 dBm)
- Duty cycle limited to **20 packets per burst** with 1ms spacing
- **Not for continuous operation** - designed for brief test bursts only
- Verify local regulations before operating
- Do not operate near sensitive equipment (medical, aviation, etc.)

---

*Generated for ESP32 Random-Channel RF Test Generator V4.1*