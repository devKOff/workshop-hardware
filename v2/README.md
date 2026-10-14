# RF Spectrum Visualizer v2

Optimized, modular re-architecture of the 2.4 GHz ISM Band Spectrum Visualizer, Analyzer, and Active Signal Mitigation system.

## Key Improvements over v1

- **Centralized Configuration**: `config.py` with typed dataclasses for all subsystems
- **Clean Interfaces**: Abstract `RadioInterface` with proper factory pattern
- **Robust Error Handling**: Custom exceptions, graceful fallbacks, detailed logging
- **Thread Safety**: RLocks throughout, callback system outside locks
- **Performance**: Optimized sweep loop with adaptive timing, numpy operations
- **Modularity**: Each component independently testable
- **Type Hints**: Full type annotations for IDE support

## File Structure

```
v2/
├── config.py              # Centralized configuration
├── hardware_radio.py      # nRF24L01+ SPI interface with fallback
├── sim_radio.py           # Realistic ISM band simulation
├── scanner.py             # Thread-safe spectrum data + high-speed scanner
├── mitigation.py          # Active mitigation with audit logging
├── app.py                 # Tkinter GUI with Matplotlib
├── cli_scan.py            # Headless terminal analyzer
├── __init__.py            # Package exports
├── requirements.txt       # Dependencies
└── tools/
    └── check_pyrf24_api.py   # Hardware diagnostics
```

## Installation

```bash
cd v2
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo raspi-config nonint do_spi 0  # Enable SPI
```

## Usage

### GUI Application
```bash
python app.py
```

### CLI Scanner
```bash
# Simulation
python cli_scan.py --sim

# Hardware
python cli_scan.py --hw

# With mitigation
python cli_scan.py --hw --mitigate -t 1,6,11 --threshold -45 --type carrier
```

### Diagnostic Tool
```bash
python tools/check_pyrf24_api.py --device /dev/spidev0.0
```

## Configuration

All settings via `config.py` dataclasses or environment variables:
- `RF_CE_PIN`, `RF_CSN_PIN`, `RF_SPI_DEVICE`, `RF_MIT_THRESHOLD`

## Architecture Highlights

### Radio Layer
- `RadioInterface` protocol for hardware/simulation parity
- `RadioFactory.create_with_fallback()` auto-falls back to sim
- Explicit SPI device selection (`/dev/spidev0.0` for CE0)

### Scanner
- `SpectrumData`: Thread-safe with callbacks, EMA, peak-hold decay, waterfall
- `ScannerThread`: Adaptive timing, error counting, pause/resume

### Mitigation
- Software interlock (explicit ARM required)
- Threshold gating with configurable targets
- Rate limiting + duration caps
- Full audit trail with reasons

### GUI
- Dark theme Matplotlib embedded in Tkinter
- Real-time spectrum + peak-hold + rolling average
- Waterfall with jet colormap
- Wi-Fi channel overlays (1, 6, 11)
- Export CSV/PNG, audit log viewer

## Hardware Wiring

| nRF24L01+ | Raspberry Pi |
|-----------|--------------|
| VCC       | 3.3V (Pin 1) |
| GND       | GND (Pin 6)  |
| CE        | GPIO25 (Pin 22) |
| CSN       | GPIO8/CE0 (Pin 24) |
| SCK       | GPIO11 (Pin 23) |
| MOSI      | GPIO10 (Pin 19) |
| MISO      | GPIO9 (Pin 21) |

## Safety

Mitigation requires:
1. Explicit ARM button press (red visual warning)
2. Configured target channels
3. Threshold exceeded on peak-hold
4. Minimum interval between actions
5. Maximum duration enforcement
6. Full audit logging

## License

MIT - Use responsibly and in compliance with local RF regulations.