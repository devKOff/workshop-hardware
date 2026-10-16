# Hardware Setup — RF Spectrum Visualizer v3.1

Raspberry Pi hardware setup for the nRF24L01+ hardware scanning mode.

## Overview

Hardware mode uses a physical nRF24L01+ radio module connected to a
Raspberry Pi via SPI. The application reads RPD (Received Power Detector)
observations from the radio via the pyrf24 Python library.

**Important:** Hardware mode is **unavailable** on this development machine
(Windows, no pyrf24, no Raspberry Pi). All hardware tests are reported as
skipped/unverified.

## Required Hardware

- Raspberry Pi (any model with SPI, e.g., Pi 3, Pi 4, Pi Zero)
- nRF24L01+ module
- Jumper wires

## Wiring (nRF24L01+ to Raspberry Pi)

| nRF24L01+ Pin | Raspberry Pi Pin | GPIO / Function |
|---------------|------------------|-----------------|
| VCC           | Pin 1            | 3.3V            |
| GND           | Pin 9            | Ground          |
| CE            | Pin 22           | GPIO 25         |
| CSN           | Pin 24           | GPIO 8 (SPI CE0)|
| SCK           | Pin 23           | GPIO 11 (SPI CLK)|
| MOSI          | Pin 19           | GPIO 10 (SPI MOSI)|
| MISO          | Pin 21           | GPIO 9 (SPI MISO)|
| IRQ           | (not used)       | —               |

The application uses CE=GPIO25, CSN=GPIO8/SPI CE0 by default, matching the
V3 source implementation.

## Software Installation (Raspberry Pi)

1. Enable SPI on the Raspberry Pi:

   ```bash
   sudo raspi-config
   # Interface Options -> SPI -> Enable
   sudo reboot
   ```

2. Install system dependencies:

   ```bash
   sudo apt update
   sudo apt install -y python3-spidev python3-dev
   ```

3. Install pyrf24:

   ```bash
   pip install pyrf24
   ```

4. Install the application dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running in Hardware Mode

1. Launch the application:

   ```bash
   python main.py
   ```

2. In the Live Spectrum page, set **Mode** to "hardware".
3. Click **Start Scan**.

If pyrf24 is not installed or the nRF24L01+ is not detected, an error
dialog is shown and the application falls back gracefully. No crash occurs.

## Troubleshooting

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| "pyrf24 not installed" | pyrf24 missing | `pip install pyrf24` |
| "nRF24L01+ not responding" | Wiring or SPI issue | Check connections, ensure SPI enabled |
| "SPI initialization failed" | SPI not enabled | `sudo raspi-config` → enable SPI, reboot |
| Permission denied on SPI device | User not in spi group | `sudo usermod -a -G spi $user`, reboot |

## Hardware Limitations

- The nRF24L01+ provides RPD (Received Power Detector) observations only —
  not calibrated dBm measurements.
- Activity percentage is computed from RPD sample counts
  (positive / valid samples), not absolute power.
- No frequency calibration beyond the standard `2400 + channel_number` MHz
  mapping.
- Only one channel can be scanned at a time; full 0–125 scan takes
  approximately `channels × measurement_window` seconds.

## Source Preservation

The original V3 (`workshop/v3`) and V6 (`workshop/v6`) projects are never
modified. V3 scanner code is imported read-only via `v3_bridge.py`.
