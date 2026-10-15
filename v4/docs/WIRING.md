# Wiring Guide

## ESP32 DevKit to nRF24L01+ Connections

```
ESP32 DevKit          nRF24L01+ Module
─────────────         ──────────────
3V3        ──────────  VCC (Pin 1)  ◄── 10-47µF capacitor to GND
GND        ──────────  GND (Pin 2)
GPIO 25    ──────────  CE  (Pin 3)
GPIO 5     ──────────  CSN (Pin 4)
GPIO 18    ──────────  SCK (Pin 5)
GPIO 23    ──────────  MOSI (Pin 6)
GPIO 19    ──────────  MISO (Pin 7)
```

## Push Button

```
ESP32 DevKit
─────────────
GPIO 4     ────────── Button ────────── GND
           (INPUT_PULLUP enabled)
```

## Optional Status LED

```
ESP32 DevKit          LED
─────────────         ───
GPIO 2     ────────── Anode (+) via 330Ω resistor
GND        ────────── Cathode (-)
```

## Power Supply Considerations

### ⚠️ Critical: Do not power nRF24L01+ from 5V
The nRF24L01+ requires 1.9-3.6V. Connecting VCC to 5V will destroy the module.

### ESP32 3.3V Regulator Limitations
The onboard 3.3V regulator (typically AMS1117-3.3 or similar) is rated for ~600-800mA but shares current with the ESP32 itself. During TX, the nRF24L01+ can draw 100-130mA peaks. This may cause brownouts.

**Recommended solutions:**
1. **Dedicated 3.3V LDO**: Use an AMS1117-3.3 or MCP1700-3302 powered from 5V/VIN pin
2. **Large decoupling**: 47µF electrolytic + 0.1µF ceramic directly at radio VCC/GND
3. **Short wires**: Keep power/ground wires thick and short (<10cm)

## Decoupling Capacitor Placement

```
         47µF Electrolytic
    ┌─────────────────────┐
    │  +         -        │
nRF VCC ───────┬───────── GND
    │          │
    │    0.1µF Ceramic
    │  ┌───────┴───────┐
    │  │             │
    └──┴─────────────┘
```

Place both capacitors as close to the nRF24L01+ VCC/GND pins as physically possible.

## Common ESP32 Board Variations

| Board | GPIO 2 LED | Notes |
|-------|------------|-------|
| ESP32 DevKit v1 | Blue LED on GPIO 2 | LED active-low, conflicts with boot |
| ESP32 DevKit v4 | No onboard LED on GPIO 2 | Safe for status LED |
| ESP32-C3 DevKit | Different pinout | Adjust pins in config.h |
| ESP32-S2/S3 | Different pinout | Adjust pins in config.h |

**GPIO 2 Warning:** On many ESP32 DevKit boards, GPIO 2 is connected to a blue LED (active low). This pin is also a strapping pin — holding it LOW at boot may enter download mode. The firmware initializes GPIO 2 as OUTPUT LOW (LED off) early in setup() to avoid issues.

## SPI Bus Sharing

If using other SPI devices (SD card, display, etc.):
- Each device needs its own CSN pin
- SCK, MOSI, MISO can be shared
- Call `SPI.begin()` once with all pins before initializing any device

## Grounding

All grounds must be common:
- ESP32 GND
- nRF24L01+ GND
- Button GND
- LED GND
- External 3.3V LDO GND (if used)

## Verification Checklist

Before powering on:
- [ ] nRF24L01+ VCC connected to 3.3V (NOT 5V)
- [ ] 47µF capacitor across nRF24L01+ VCC/GND
- [ ] 0.1µF capacitor across nRF24L01+ VCC/GND
- [ ] CE → GPIO 25
- [ ] CSN → GPIO 5
- [ ] SCK → GPIO 18
- [ ] MOSI → GPIO 23
- [ ] MISO → GPIO 19
- [ ] Button → GPIO 4 and GND
- [ ] LED (if used) → GPIO 2 with resistor
- [ ] All GNDs connected together
- [ ] No shorts between adjacent nRF24L01+ pins (2mm pitch!)