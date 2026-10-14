# 2.4 GHz ISM Band RF Spectrum Visualizer & Mitigation System

A production-ready, modular Python codebase for real-time RF spectrum analysis and active signal mitigation using Raspberry Pi and nRF24L01+ transceiver.

## Features

- **Real-time Spectrum Analysis**: 126-channel sweep (2400-2525 MHz) with rolling averages and peak-hold
- **Waterfall Display**: Temporal RF history visualization
- **Active Mitigation**: Carrier wave or packet noise transmission with software interlock
- **Dual Mode**: Hardware (nRF24L01+) and simulation modes
- **GUI & CLI**: Tkinter/Matplotlib GUI and headless terminal interface
- **Audit Logging**: Full mitigation event logging with timestamps

## Hardware Requirements

- Raspberry Pi (any model with SPI)
- nRF24L01+ module (with PA/LNA recommended)
- SPI wiring:
  - CE  → GPIO25 (Pin 22)
  - CSN → GPIO8/CE0 (Pin 24)
  - SCK → GPIO11 (Pin 23)
  - MOSI → GPIO10 (Pin 19)
  - MISO → GPIO9 (Pin 21)
  - VCC → 3.3V
  - GND → GND

## Installation

```bash
# Enable SPI on Raspberry Pi
sudo raspi-config  # Interface Options → SPI → Enable

# Install dependencies
pip install -r requirements.txt

# Verify hardware
python tools/check_pyrf24_api.py
```

## Usage

### GUI Application
```bash
python app.py
```

### CLI Scanner (Headless/SSH)
```bash
# Simulation mode
python cli_scan.py --sim

# Hardware mode
python cli_scan.py --hw

# With mitigation
python cli_scan.py --hw --mitigate -t 1,6,11 --threshold -45 --type carrier
```

### Diagnostic Tool
```bash
python tools/check_pyrf24_api.py
```

## Architecture

```
hardware_radio.py   → Low-level nRF24L01+ SPI interface
sim_radio.py        → Realistic 2.4 GHz traffic simulation
scanner.py          → Thread-safe spectrum data + high-speed scanner
mitigation.py       → Active countermeasures with audit logging
app.py              → Tkinter GUI with Matplotlib plots
cli_scan.py         → Terminal-based ASCII spectrum analyzer
tools/check_pyrf24_api.py  → Hardware diagnostics
```

## Mitigation Safety

The mitigation system includes multiple safety layers:
1. **Software Interlock**: Explicit `ARM` required before any transmission
2. **Threshold Gating**: Only triggers above user-defined power threshold
3. **Rate Limiting**: Minimum interval between mitigation events
4. **Duration Limits**: Maximum transmission duration enforced
5. **Audit Trail**: All events logged with timestamps and parameters

## Channel Mapping

| Channel | Frequency | Notes |
|---------|-----------|-------|
| 0-125   | 2400-2525 MHz | nRF24L01+ native channels |
| 1       | 2412 MHz      | Wi-Fi Channel 1 |
| 6       | 2437 MHz      | Wi-Fi Channel 6 |
| 11      | 2462 MHz      | Wi-Fi Channel 11 |

## License

MIT License - Use responsibly and in compliance with local RF regulations.