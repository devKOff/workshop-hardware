# RF Spectrum Visualizer v6

A production-ready 2.4 GHz RF Spectrum Visualizer for nRF24L01+ with persistent blocklist, channel avoidance, deterministic simulation, and comprehensive CLI/GUI interfaces.

## Features

- **126-Channel Scanning**: Full 0-125 nRF24L01+ channel range (2400-2525 MHz)
- **Persistent JSON Blocklist**: Atomic writes, survives restarts, corruption recovery
- **Channel Avoidance Algorithm**: Ranks channels by activity, excludes blocked/high-activity/insufficient-data channels
- **Deterministic Simulation**: Reproducible scenarios with fixed seeds (quiet, busy, spikes, WiFi-like, channel 122 variations)
- **Hardware Support**: Raspberry Pi 3B+ with nRF24L01+ (CE=GPIO25, CSN=GPIO8/SPI CE0)
- **Graceful Hardware Failure**: Clear errors when pyrf24/SPI unavailable, no silent fallback
- **CSV/JSON Exports**: Full spectrum data, blocklist, waterfall history
- **Tkinter GUI**: Real-time spectrum, waterfall, channel table with sorting/filtering, blocklist controls
- **Comprehensive CLI**: block, unblock, blocklist, channel, channels, recommend, scan, export, simulate, diagnostic
- **Full Test Suite**: pytest coverage for all modules, regression tests, persistence validation

## Quick Start

### Installation

```bash
cd v6
pip install -r requirements.txt
```

### Simulation Mode (No Hardware Required)

```bash
# Run deterministic simulation
python -m v6.cli_scan simulate --scenario mixed --seed 42

# Continuous scanning with table output
python -m v6.cli_scan scan --format table

# Single scan and exit
python -m v6.cli_scan scan --single --format json
```

### GUI Mode

```bash
python -m v6.app
```

### Hardware Mode (Raspberry Pi 3B+)

```bash
# Requires pyrf24 and SPI enabled
sudo raspi-config  # Enable SPI
pip install pyrf24 spidev

# Run with hardware backend
python -m v6.cli_scan scan --backend hardware
python -m v6.app  # GUI with hardware backend selection
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `scan` | Continuous scanning (table/ascii/json/csv output) |
| `scan --single` | Single scan pass then exit |
| `block <channel>` | Block a channel (e.g., `122`, `Ch 122`, `2522 MHz`) |
| `unblock <channel>` | Unblock a channel |
| `blocklist` | Show all blocked channels |
| `channel <channel>` | Check block status of a channel |
| `channels` | List all 126 channels with block status |
| `recommend [--count N]` | Get top N channel recommendations |
| `export [--format json|csv|all] [--output FILE]` | Export scan data |
| `simulate --scenario <name>` | Run deterministic simulation |
| `diagnostic [--test-hardware]` | Hardware availability check |

### Simulation Scenarios

- `quiet` - All channels <5% activity
- `single_busy` - One channel at 80%, rest quiet
- `spikes` - Random activity spikes
- `channel_122_high` - Channel 122 consistently high (85%)
- `channel_122_low` - Channel 122 consistently low (2%)
- `wifi_like` - WiFi channels 1,6,11 (nRF 12,37,62) active
- `frequency_hopping` - Hopping pattern on some channels
- `sensor_errors` - Random sensor failures (1%)
- `mixed` - Realistic mixed environment (default)

## Blocklist Workflow

```bash
# Block channel 122
python -m v6.cli_scan block 122 --reason "Interference source"

# Verify blocked
python -m v6.cli_scan channel 122
# Output: Channel: Ch 122 (2522 MHz), Blocked: YES

# Check recommendations (122 excluded)
python -m v6.cli_scan recommend --count 5

# Restart application - block persists
python -m v6.cli_scan channel 122
# Still shows: Blocked: YES

# Unblock when clear
python -m v6.cli_scan unblock 122
python -m v6.cli_scan channel 122
# Output: Channel: Ch 122 (2522 MHz), Blocked: NO
```

## GUI Features

- **Blocklist Controls**: Numeric input + Block/Unblock/Check buttons with persistence verification
- **Channel Table**: 126-channel scrollable table with sorting (click headers), search, status filters
- **Live Spectrum**: Real-time bar graph with WiFi channel markers and threshold lines
- **Waterfall**: Time vs frequency heatmap
- **Recommendations Panel**: Top eligible channels with activity percentages
- **Export Buttons**: One-click JSON/CSV/PNG export
- **Simulation Scenarios**: Tools menu for deterministic testing

## Hardware Wiring (Raspberry Pi 3B+)

| nRF24L01+ Pin | Raspberry Pi GPIO | Physical Pin |
|---------------|-------------------|--------------|
| VCC | 3.3V | 1 or 17 |
| GND | GND | 6, 9, 14, 20, 25, 30, 34, 39 |
| CE | GPIO 25 | 22 |
| CSN | GPIO 8 (SPI CE0) | 24 |
| SCK | GPIO 11 | 23 |
| MOSI | GPIO 10 | 19 |
| MISO | GPIO 9 | 21 |

## Project Structure

```
v6/
├── README.md
├── requirements.txt
├── .gitignore
├── config.py              # Configuration dataclasses
├── exceptions.py          # Custom exception hierarchy
├── channel_utils.py       # Channel/frequency conversion, validation
├── blocklist_manager.py   # Persistent JSON blocklist with atomic writes
├── channel_selector.py    # Channel avoidance & recommendation algorithm
├── hardware_radio.py      # pyrf24 wrapper for Pi 3B+
├── sim_radio.py           # Deterministic simulation engine
├── scanner.py             # ScannerThread & SpectrumData
├── report_generator.py    # CSV/JSON export
├── logging_config.py      # JSON Lines logging
├── cli_scan.py            # Comprehensive CLI
├── app.py                 # Tkinter GUI application
├── tests/
│   ├── test_channel_utils.py
│   ├── test_blocklist_manager.py
│   ├── test_channel_selector.py
│   ├── test_scanner.py
│   ├── test_simulation.py
│   ├── test_exports.py
│   ├── test_cli.py
│   ├── test_gui_logic.py
│   ├── test_error_handling.py
│   └── test_regression.py
└── tools/
    ├── check_pyrf24_api.py
    └── run_validation.py
```

## Running Tests

```bash
# Run all tests
python -m pytest v6/tests -v

# Run specific test module
python -m pytest v6/tests/test_blocklist_manager.py -v

# Run validation suite
python v6/tools/run_validation.py
```

## Configuration

All settings via `config.py` dataclasses or CLI arguments:

- **ChannelConfig**: start/end channel (0-125)
- **ScanConfig**: measurement_window, sampling_interval, min_valid_samples
- **ThresholdConfig**: clear/moderate/busy/heavy thresholds (0-100%)
- **BlocklistConfig**: file_path, atomic_writes
- **SimConfig**: seed, deterministic
- **HardwareConfig**: ce_pin, csn_pin, spi_speed

## Logging

JSON Lines format to `v6/logs/countermeasures.jsonl` with structured fields for:
- Countermeasure events (alerts, recommendations)
- Scanner errors
- Hardware diagnostics

## Known Limitations

1. **nRF24L01+ RPD is not calibrated power** - only relative activity detection
2. **Single-channel measurement** - nRF24L01+ tunes to one channel at a time
3. **Simulation is model-based** - not real RF propagation
4. **Hardware requires Raspberry Pi** - no support for other SBCs without modification
5. **GUI requires display** - headless operation via CLI only
6. **Blocklist is local JSON** - no distributed synchronization

## License

MIT License - See LICENSE file for details.

## Version History

- **v6**: Complete rewrite with persistent blocklist, deterministic simulation, channel avoidance, full test suite
- **v3**: Previous version with basic scanning, mitigation, matplotlib GUI