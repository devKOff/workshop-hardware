# RF Spectrum Visualizer - 2.4 GHz ISM Band Monitor

A complete Python application for monitoring and visualizing RF activity in the 2.4 GHz ISM band using a Raspberry Pi 3B+ and nRF24L01+ transceiver, with a fully functional simulation mode for development and testing.

## Features

- **Dual Backend Architecture**: Hardware mode (physical nRF24L01+) and Simulation mode (deterministic RF models)
- **Full Channel Scanning**: Scans all 126 standard nRF24L01+ channels (0-125) by default
- **Per-Channel Activity Display**: Terminal-based Unicode activity bars with percentages and classifications
- **Live GUI**: Tkinter + Matplotlib with spectrum graph, waterfall visualization, and channel table
- **Wi-Fi Reference Overlays**: Shows Wi-Fi channels 1, 6, 11 at 2412/2437/2462 MHz
- **Threshold-Based Alerts**: Configurable activity classification (Clear/Moderate/Busy/Heavy Load)
- **Persistent Activity Detection**: Tracks sustained high activity with cooldown and hysteresis
- **Safe Recommendations**: Suggests lower-activity alternative channels (no interference)
- **Export**: CSV, JSON Lines, and PNG exports
- **Comprehensive Testing**: Unit, integration, concurrency, and regression tests

## Hardware Requirements

- Raspberry Pi 3B+ (or compatible)
- nRF24L01+ 2.4 GHz transceiver module
- Raspberry Pi OS with SPI enabled
- 3.3V power supply (NOT 5V!)

### Wiring

| nRF24L01+ Pin | Raspberry Pi GPIO | Description |
|--------------|-------------------|-------------|
| VCC | 3.3V (Pin 1/17) | Power - **3.3V ONLY** |
| GND | GND (Pin 6/9/14/20/25/30/34/39) | Ground |
| CE | GPIO25 (Pin 22) | Chip Enable |
| CSN | GPIO8 / SPI CE0 (Pin 24) | Chip Select Not |
| SCK | GPIO11 (Pin 23) | SPI Clock |
| MOSI | GPIO10 (Pin 19) | SPI Master Out Slave In |
| MISO | GPIO9 (Pin 21) | SPI Master In Slave Out |
| IRQ | Not connected | Interrupt (unused) |

## Installation

### Raspberry Pi OS (Hardware Mode)

```bash
# Enable SPI
sudo raspi-config
# Interface Options -> SPI -> Enable -> Reboot

# Install system dependencies
sudo apt update
sudo apt install python3-spidev python3-dev python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install pyrf24 (may need to build from source)
pip install pyrf24

# Install Python dependencies
pip install -r requirements.txt
```

### Linux Desktop / Windows (Simulation Mode Only)

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

## Usage

### Command Line Interface

```bash
# Simulation mode (default)
python cli_scan.py --backend sim

# Hardware mode (requires nRF24L01+)
python cli_scan.py --backend hardware

# Custom scan duration
python cli_scan.py --backend sim --duration 30

# JSON output for piping
python cli_scan.py --backend sim --format json

# With mitigation alerts (ARMED mode)
python cli_scan.py --backend sim --mitigate --threshold 60

# Custom channel range
python cli_scan.py --backend sim --start-channel 0 --end-channel 125

# Run hardware diagnostic
python cli_scan.py --diagnostic
```

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--backend` | `sim` or `hardware` | `sim` |
| `--start-channel` | First channel to scan (0-125) | `0` |
| `--end-channel` | Last channel to scan (0-125) | `125` |
| `--window` | Measurement window per channel (seconds) | `1.0` |
| `--interval` | Sampling interval (seconds) | `0.01` |
| `--min-samples` | Minimum valid samples for calculation | `10` |
| `--clear-max` | Clear status max % | `24` |
| `--moderate-max` | Moderate status max % | `49` |
| `--busy-max` | Busy status max % | `74` |
| `--heavy-min` | Heavy Load status min % | `75` |
| `--persistent-threshold` | Persistent activity threshold % | `75.0` |
| `--persistence-duration` | Duration for persistent detection (s) | `10.0` |
| `--consecutive-windows` | Consecutive windows for persistence | `3` |
| `--alert-cooldown` | Alert cooldown (seconds) | `30.0` |
| `--hysteresis` | Hysteresis for alert clearing | `5.0` |
| `--mitigate` | Enable ARMED mode (alerts + recommendations) | `False` |
| `--format` | Output: `table`, `ascii`, `json`, `csv` | `table` |
| `--sort` | Sort by: `channel`, `activity`, `status` | `channel` |
| `--log-path` | Countermeasures log file | `logs/countermeasures.jsonl` |
| `--export-dir` | Export directory | `exports` |
| `-v, --verbose` | Increase verbosity | `-` |

### GUI Application

```bash
# Simulation mode
python app.py

# Hardware mode
python app.py --hardware
```

#### GUI Features

- **Toolbar**: Backend selector, Start/Stop, channel range, timing controls, ARMED toggle
- **Channel Table**: Scrollable table with all channels, activity bars, percentages, sample counts
- **Spectrum Graph**: Live bar graph of activity percentages with threshold markers
- **Waterfall**: Time vs frequency heatmap with configurable history depth
- **Alerts Panel**: Real-time alerts and diagnostic messages
- **Export Buttons**: CSV, JSON, PNG (spectrum/waterfall)
- **Menu**: File exports, View options, Help

### Hardware Diagnostic Tool

```bash
python tools/check_pyrf24_api.py
```

Checks:
- Python version
- pyrf24 installation and API
- SPI device availability
- GPIO access
- Hardware initialization (read-only test)

## Channel Mapping

The nRF24L01+ uses 126 channels (0-125) at 1 MHz spacing:

| nRF24 Channel | Center Frequency | Notes |
|--------------|------------------|-------|
| 0 | 2400 MHz | Band start |
| 12 | 2412 MHz | **Wi-Fi Channel 1** |
| 37 | 2437 MHz | **Wi-Fi Channel 6** |
| 62 | 2462 MHz | **Wi-Fi Channel 11** |
| 76 | 2476 MHz | Common nRF24 default |
| 125 | 2525 MHz | Band end |

**Formula**: `frequency_mhz = 2400 + channel_number`

**Important**: These are nRF24 channel numbers, NOT Wi-Fi channel numbers.

## Activity Measurement

The nRF24L01+ provides binary RPD (Received Power Detector) readings - it detects whether energy is present above a threshold (~ -50 dBm), not calibrated power levels.

### Activity Percentage Calculation

```
activity_percentage = (RPD_positive_count / valid_sample_count) × 100
```

- **RPD_positive**: Number of samples where energy was detected
- **valid_sample_count**: Total successful RPD readings in the measurement window
- **Measurement window**: Default 1.0 second per channel
- **Sampling interval**: Default 10 ms (100 samples/window)

### Status Classifications

| Percentage | Status | Meaning |
|------------|--------|---------|
| 0-24% | Clear | Low observed activity |
| 25-49% | Moderate | Some activity detected |
| 50-74% | Busy | Significant activity |
| 75-100% | Heavy Load | Sustained high activity |
| N/A | INSUFFICIENT DATA | Below minimum sample count |

### Limitations

- **Not a spectrum analyzer**: nRF24L01+ is a narrowband transceiver
- **No dBm calibration**: RPD is binary (energy detected / not detected)
- **No protocol decoding**: Cannot identify Wi-Fi, Bluetooth, Zigbee, etc.
- **Single frequency at a time**: Scans channels sequentially
- **Antenna dependent**: Results vary with antenna type and placement

## Mitigation System

The mitigation subsystem is **passive only** - it never transmits or interferes.

### States

- **DISARMED** (default): Passive observation and logging only
- **ARMED**: Enables threshold alerts, persistent activity detection, and safe channel recommendations

### Detection

- Activity threshold: Default 75%
- Persistence duration: Default 10 seconds
- Consecutive windows: Default 3
- Alert cooldown: Default 30 seconds
- Hysteresis: Default 5%

### Recommendations

When persistent activity is detected, the system suggests up to 5 alternative channels with lower observed activity, sorted by activity percentage.

## Logging

Countermeasures events logged to `logs/countermeasures.jsonl` (JSON Lines format):

```json
{
  "timestamp": "2026-10-14T12:34:56.789Z",
  "level": "INFO",
  "logger": "rf_visualizer.mitigation",
  "message": "Countermeasure event",
  "event_id": "a1b2c3d4",
  "event_type": "PERSISTENT_HIGH_ACTIVITY",
  "backend": "sim",
  "channel": 12,
  "frequency_mhz": 2412,
  "activity_percentage": 85.5,
  "sample_count": 100,
  "rpd_positive_count": 85,
  "measurement_window": 1.0,
  "threshold": 75.0,
  "classification": "Heavy Load",
  "recommended_response": "Consider channels: [13, 14, 15, 11, 10]",
  "action_status": "ALERT_GENERATED"
}
```

## Exports

### CSV Export

```csv
timestamp,channel,frequency_mhz,backend,valid_samples,rpd_positive,rpd_negative,activity_percentage,status,data_sufficient,measurement_window,sampling_interval,error
1234567890.0,12,2412,sim,100,68,32,68.0,Busy,True,1.0,0.01,
```

### JSON Export

```json
{
  "config": { "backend": "sim", "channel_range": [0, 125], ... },
  "scan_count": 5,
  "observations": [...]
}
```

### PNG Export

Saves current spectrum or waterfall visualization via file dialog.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_spectrum_data.py -v
pytest tests/test_sim_radio.py -v
pytest tests/test_hardware_radio.py -v
pytest tests/test_scanner.py -v
pytest tests/test_mitigation.py -v
pytest tests/test_cli_scan.py -v
pytest tests/test_gui.py -v
pytest tests/test_concurrency.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Test Categories

- **Unit tests**: Channel math, activity calculations, configuration validation
- **Simulation tests**: Deterministic reproduction, pattern modeling
- **Hardware tests**: Mocked pyrf24, SPI error handling
- **Scanner tests**: Thread lifecycle, callbacks, concurrent access
- **Mitigation tests**: Alert generation, cooldown, hysteresis, recommendations
- **CLI tests**: Argument parsing, output formats, exports
- **GUI tests**: Import without display, component initialization
- **Concurrency tests**: Thread safety, snapshot consistency, lock behavior

## Configuration

All settings in `config.py`:

```python
AppConfig(
    channel=ChannelConfig(start_channel=0, end_channel=125),
    scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01, min_valid_samples=10),
    thresholds=ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=75),
    mitigation=MitigationConfig(persistent_threshold=75.0, persistence_duration=10.0, ...),
    storage=StorageConfig(rolling_history_size=100, waterfall_history_size=200),
    gui=GUIConfig(refresh_interval_ms=500),
    default_backend="sim"
)
```

## Architecture

```
rf-spectrum-visualizer/
├── scanner.py           # SpectrumData, ScannerThread
├── hardware_radio.py    # HardwareRadio (pyrf24)
├── sim_radio.py         # SimRadio (deterministic simulation)
├── mitigation.py        # MitigationEngine (alerts, recommendations)
├── app.py               # Tkinter GUI with Matplotlib
├── cli_scan.py          # Command-line interface
├── config.py            # Configuration dataclasses
├── exceptions.py        # Custom exception hierarchy
├── logging_config.py    # JSON Lines logging
├── requirements.txt     # Dependencies
├── tools/
│   └── check_pyrf24_api.py  # Hardware diagnostic
└── tests/
    ├── test_spectrum_data.py
    ├── test_hardware_radio.py
    ├── test_sim_radio.py
    ├── test_scanner.py
    ├── test_mitigation.py
    ├── test_cli_scan.py
    ├── test_gui.py
    └── test_concurrency.py
```

## Validation

Two-pass validation process:

### Pass 1 - Functional Correctness
1. Syntax compilation
2. Module imports
3. Configuration validation
4. Unit tests
5. Full-range simulation scan (channels 0-125)
6. CLI output format tests
7. GUI initialization tests
8. Export tests
9. API diagnostic tests

### Pass 2 - Reliability & Regression
1. Complete test suite rerun
2. Repeated start/stop stress tests
3. Concurrent snapshot/update tests
4. Worker exception recovery
4. GUI callback cancellation
5. Simulation reproducibility
6. Full-range channel coverage
7. Resource cleanup
8. Export completeness and percentage verification
9. Import isolation
10. Final repository review

## Troubleshooting

### Hardware Mode Issues

| Problem | Solution |
|---------|----------|
| "pyrf24 not installed" | `pip install pyrf24` or build from source |
| "SPI initialization failed" | Enable SPI in raspi-config, reboot |
| "nRF24L01+ not responding" | Check wiring, verify 3.3V power, check CE/CSN pins |
| "Permission denied /dev/spidev" | Add user to spi group: `sudo usermod -a -G spi $USER` |
| "Permission denied /dev/gpiomem" | Add user to gpio group: `sudo usermod -a -G gpio $USER` |

### Simulation Mode Issues

| Problem | Solution |
|---------|----------|
| Import errors | Install requirements: `pip install -r requirements.txt` |
| GUI won't start | Ensure tkinter installed (usually included with Python) |
| Matplotlib errors | Install matplotlib: `pip install matplotlib` |

## License

MIT License - See LICENSE file for details.

## Disclaimer

This software is for educational and diagnostic purposes only. The nRF24L01+ is not a calibrated spectrum analyzer. Measurements represent relative RF energy detection observations under specific sampling conditions. Do not use for regulatory compliance testing or safety-critical applications.

The mitigation system provides **passive recommendations only** and never transmits interfering signals.