# RF Spectrum Visualizer Project Consolidated

A comprehensive RF spectrum analysis tool for the 2.4 GHz ISM band, evolved through multiple iterations from a basic spectrum analyzer to a fully-featured application with channel avoidance, persistent blocklist, anomaly detection, and simulation capabilities.

---

## 📖 Project Overview

The RF Spectrum Visualizer has undergone significant evolution across multiple versions, each adding new capabilities, improving architecture, and refining the user experience. This project consolidates all source code, scripts, and documentation from 12 version folders (`v1` through `v7.1` plus the main `rf_spectrum_visualizer` implementation) into a single, organized repository that documents the complete chronological development history.

The project traces its lineage from the original 2.4 GHz ISM band spectrum analyzer (v1) through modular re-architecture (v2), dual-backend implementation (v3), anomaly detection (v5), production release with channel avoidance (v6), to the standalone Raspberry Pi visualizer (v7/v7.1), culminating in the unified main implementation that integrates the best features from all preceding versions.

---

## 🕐 Chronological Development Phases

### Phase 1: v1 — Original Spectrum Visualizer & Mitigation System (Oct 14, 2026)

The foundation of the project. v1 introduced the core concept of real-time RF spectrum analysis with active signal mitigation.

**Key Features:**
- Real-time spectrum analysis with 126-channel sweep (2400-2525 MHz)
- Waterfall display with rolling averages and peak-hold
- Active mitigation: carrier wave or packet noise transmission with software interlock
- Dual mode: Hardware (nRF24L01+) and simulation modes
- GUI & CLI: Tkinter/Matplotlib GUI and headless terminal interface
- Audit logging: Full mitigation event logging with timestamps

**Core Files:**
- `app.py` — Tkinter GUI with Matplotlib plots
- `cli_scan.py` — Terminal-based ASCII spectrum analyzer
- `hardware_radio.py` — Low-level nRF24L01+ SPI interface
- `sim_radio.py` — Realistic 2.4 GHz traffic simulation
- `scanner.py` — Thread-safe spectrum data + high-speed scanner
- `mitigation.py` — Active countermeasures with audit logging
- `tools/check_pyrf24_api.py` → Hardware diagnostics

**Dependencies:**
- matplotlib, numpy
- Optional: pyrf24 (for hardware mode)

**Usage:**
```bash
python app.py                    # GUI application
python cli_scan.py --sim        # Simulation mode
python cli_scan.py --hw          # Hardware mode
```

---

### Phase 2: v2 — Modular Re-architecture with Type Safety (Oct 15, 2026)

A complete rewrite focused on modularity, error handling, and type safety. This version established the patterns that would persist throughout the project's evolution.

**Key Improvements over v1:**
- Centralized configuration: `config.py` with typed dataclasses for all subsystems
- Clean interfaces: Abstract `RadioInterface` with proper factory pattern
- Robust error handling: Custom exceptions, graceful fallbacks, detailed logging
- Thread safety: RLocks throughout, callback system outside locks
- Performance: Optimized sweep loop with adaptive timing, numpy operations
- Modularity: Each component independently testable
- Type hints: Full type annotations for IDE support

**File Structure:**
```
v2/
├── config.py              # Centralized configuration
├── hardware_radio.py      # nRF24L01+ SPI interface with fallback
├── sim_radio.py           # Realistic ISM band simulation
├── scanner.py             # Thread-safe spectrum data + high-speed scanner
├── mitigation.py          # Active mitigation with audit logging
├── app.py                 # Tkinter GUI with Matplotlib
├── cli_scan.py            # Headline terminal analyzer
├── __init__.py            # Package exports
├── requirements.txt       # Dependencies
└── tools/
    └── check_pyrf24_api.py   # Hardware diagnostics
```

**Dependencies:**
- All v1 dependencies plus full type hinting support

**Usage:**
```bash
python app.py
python cli_scan.py --sim
python cli_scan.py --hw --mitigate -t 1,6,11 --threshold -45 --type carrier
```

---

### Phase 3: v3 — Dual Backend Architecture & Comprehensive Testing (Oct 16, 2026)

Version 3 represented a major leap forward with a proper dual backend architecture (hardware + simulation), comprehensive testing, and the introduction of many features that define the project today.

**Key Features:**
- Dual Backend Architecture: Hardware mode (physical nRF24L01+) and Simulation mode (deterministic RF models)
- Full Channel Scanning: Scans all 126 standard nRF24L01+ channels (0-125) by default
- Per-Channel Activity Display: Terminal-based Unicode activity bars with percentages and classifications
- Live GUI: Tkinter + Matplotlib with spectrum graph, waterfall visualization, and channel table
- Wi-Fi Reference Overlays: Shows Wi-Fi channels 1, 6, 11 at 2412/2437/2462 MHz
- Threshold-Based Alerts: Configurable activity classification (Clear/Moderate/Busy/Heavy Load)
- Persistent Activity Detection: Tracks sustained high activity with cooldown and hysteresis
- Safe Recommendations: Suggests lower-activity alternative channels (no interference)
- Export: CSV, JSON Lines, and PNG exports
- Comprehensive Testing: Unit, integration, concurrency, and regression tests (8 test modules)

**Configuration Structure:**
```python
AppConfig(
    channel=ChannelConfig(start_channel=0, end_channel=125),
    scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01, min_valid_samples=10),
    thresholds=ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=75),
    mitigation=MitigationConfig(persistent_threshold=75.0, persistence_duration=10.0),
    storage=StorageConfig(rolling_history_size=100, waterfall_history_size=200),
    gui=GUIConfig(refresh_interval_ms=500),
    default_backend="sim"
)
```

**Test Suite (8 modules):**
- `test_spectrum_data.py` - ChannelObservation, SpectrumData, configs
- `test_sim_radio.py` - SimRadio, ChannelModel, reproducibility
- `test_hardware_radio.py` - Mocked pyrf24 tests
- `test_scanner.py` - ScannerThread lifecycle, callbacks, concurrency
- `test_mitigation.py` - Alert generation, cooldown, hysteresis
- `test_cli_scan.py` - Display rendering, exports, arg parsing
- `test_gui.py` - Mocked GUI components, headless import
- `test_concurrency.py` - Thread safety, lock contention, callbacks

**Dependencies:**
- matplotlib, numpy, pytest, pytest-cov
- Optional: pyrf24 (for hardware mode)

**Usage:**
```bash
# CLI (simulation mode)
python cli_scan.py --backend sim
python cli_scan.py --backend sim --format json

# GUI (simulation mode)
python app.py

# GUI (hardware mode - requires Raspberry Pi)
python app.py --hardware
```

**Notable New Files:**
- `exceptions.py` - Custom exception hierarchy
- `logging_config.py` - JSON Lines logging
- `PROJECT_SUMMARY.txt` - Project documentation
- Full test suite directory structure

---

### Phase 4: v3.1 — Blocklist Exclusions Patch (Oct 17, 2026)

A minor update to v3 that added blocklist exclusion functionality.

**Key Changes:**
- Added `blocker_exclusions.json` for configuring channels that should never be blocked
- Minor bug fixes and stability improvements
- Backward compatible with v3 project structure

**New File:**
- `blocker_exclusions.json` - Channel exclusion configuration

---

### Phase 5: v5 — Anomaly Detection & Channel Classification (Oct 15, 2026)

Version 5 introduced advanced signal processing capabilities, including anomaly detection and channel classification, expanding the project's analytical capabilities beyond simple activity monitoring.

**Key Features:**
- Anomaly Detection Engine: `anomaly_detector.py` - Detects unusual RF patterns and anomalies
- Channel Classifier: `channel_classifier.py` - Activity classification & recommendations
- Simulation Scenarios: Test specific scenarios (persistent_busy, sudden_spike, hopping_like)
- New Configuration Structure: AnomalyConfig and SimulationConfig added to `config.py`
- Enhanced Report Generation: `report_generator.py` - CSV/JSON/JSONL/PNG export
- Advanced CLI: `--test-scenario` option for deterministic testing

**New Modules:**
- `anomaly_detector.py` - Anomaly detection engine
- `channel_classifier.py` - Activity classification & recommendations
- `report_generator.py` - CSV/JSON/JSONL/PNG export functionality
- Updated `config.py` with `AnomalyConfig` and `SimulationConfig`

**Simulation Scenarios:**
```bash
python cli_scan.py --test-scenario persistent_busy
python cli_scan.py --test-scenario sudden_spike
python cli_scan.py --test-scenario hopping_like
python -c "from sim_radio import SimRadio; print(SimRadio.get_available_scenarios())"
```

**Dependencies:**
- All v3 dependencies plus any anomaly detection specific libraries

**Usage:**
```bash
python cli_scan.py --test-scenario mixed
python app.py --sim
```

---

### Phase 6: v6 — Production Release with Persistent Blocklist & Channel Avoidance (Oct 17, 2026)

Version 6 was the first version branded specifically as "RF Spectrum Visualizer v6" and introduced the persistent JSON blocklist, channel avoidance algorithm, and the CLI command structure that remains central to the project.

**Key Features:**
- 126-Channel Scanning: Full 0-125 nRF24L01+ channel range (2400-2525 MHz)
- Persistent JSON Blocklist: Atomic writes, survives restarts, corruption recovery
- Channel Avoidance Algorithm: Ranks channels by activity, excludes blocked/high-activity/insufficient-data channels
- Deterministic Simulation: Reproducible scenarios with fixed seeds (quiet, busy, spikes, WiFi-like, channel 122 variations)
- Hardware Support: Raspberry Pi 3B+ with nRF24L01+ (CE=GPIO25, CSN=GPIO8/SPI CE0)
- Graceful Hardware Failure: Clear errors when pyrf24/SPI unavailable, no silent fallback
- CSV/JSON Exports: Full spectrum data, blocklist, waterfall history
- Tkinter GUI: Real-time spectrum, waterfall, channel table with sorting/filtering, blocklist controls
- Comprehensive CLI: block, unblock, blocklist, channel, channels, recommend, scan, export, simulate, diagnostic
- Full Test Suite: pytest coverage for all modules, regression tests, persistence validation

**CLI Command Structure:**
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

**Simulation Scenarios:**
- `quiet` - All channels <5% activity
- `single_busy` - One channel at 80%, rest quiet
- `spikes` - Random activity spikes
- `channel_122_high` - Channel 122 consistently high (85%)
- `channel_122_low` - Channel 122 consistently low (2%)
- `wifi_like` - WiFi channels 1,6,11 (nRF 12,37,62) active
- `frequency_hopping` - Hopping pattern on some channels
- `sensor_errors` - Random sensor failures (1%)
- `mixed` - Realistic mixed environment (default)
- `high_activity` - All channels 30-50% activity

**Project Structure:**
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

**Dependencies:**
- matplotlib, numpy, pytest
- Optional: pyrf24 (for hardware mode)

**Usage:**
```bash
# CLI (simulation mode)
python -m v6.cli_scan scan --format table
python -m v6.cli_scan block 122 --reason "Interference source"
python -m v6.cli_scan recommend --count 5
python -m v6.cli_scan simulate --scenario mixed --seed 42

# GUI mode
python -m v6.app
```

---

### Phase 7: v7 — Standalone Raspberry Pi Visualizer (Oct 17-19, 2026)

A complete rebuild from scratch, v7 introduced a phased development approach, new launch scripts, desktop shortcuts, and modern Python packaging with pyproject.toml.

**Phased Development Roadmap:**
1. ✅ Scaffold + hardware check scripts (check_radio.py, check_rpd.py) — DONE
2. ✅ Scan backend (SimBackend / HardwareBackend, per-channel stats) — DONE
3. ✅ GUI shell + Live Spectrum page — DONE
4. ✅ Start Analysis page + CSV export — DONE
5. ✅ Blocker page + JSON persistence — DONE
6. ✅ Waterfall, scan-rate readout, Clear button, docs, launch script/desktop shortcut — DONE

**Key Features:**
- Tkinter + Matplotlib desktop app for Raspberry Pi 3B+
- Scans nRF24L01+ channels 0-125 (2400-2525 MHz)
- Three main pages: Live Spectrum, Start Analysis, Blocker
- Software-level channel exclusion (saved to disk, restored on restart)
- NOT an SDR: nRF24L01+ is a narrowband transceiver, reports one bit per channel (RPD)
- Activity metric: Activity % = (samples with RPD true / total samples) x 100
- Six-phase development documented in `docs/PROGRESS.md`

**New Directories & Files:**
- `scripts/` - Launch scripts and desktop shortcuts
  - `run_gui.py` — launches the GUI with optional file logging
  - `check_radio.py` — Phase 1: verify the radio
  - `check_rpd.py` — Phase 1: RPD activity on sample channels
  - `rf_spectrum_visualizer.desktop` — desktop shortcut for autostart
- `docs/` - Documentation
  - `hardware_check.md` - Hardware verification guide
  - `phase6.md` - Phase 6 documentation
  - `PROGRESS.md` - Phased development progress
- `pyproject.toml` - Modern Python package configuration
- `scripts/run_gui.py` — Launch script with venv activation

**Setup & Installation:**
```bash
# Enable SPI
sudo raspi-config   # Interface Options -> SPI -> Enable
sudo reboot

# Install dependencies
sudo apt update
sudo apt install -y python3-spidev python3-dev python3-tk python3-pip
pip install pyrf24 matplotlib

# Recommended: SPI without sudo
sudo usermod -a -G spi $USER
# log out and back in
```

**Run the Application:**
```bash
source .venv/bin/activate          # if using a venv
export PYTHONPATH="src"
python scripts/run_gui.py          # Phase 6: launch the GUI
python scripts/check_radio.py      # Phase 1: verify the radio
python scripts/check_rpd.py        # Phase 1: RPD activity on sample channels
```

**Testing:**
```bash
pip install -e ".[dev]"
pytest
```

**Roadmap (phases - all DONE):**
1. Scaffold + hardware check scripts — DONE
2. Scan backend (SimBackend / HardwareBackend) — DONE
3. GUI shell + Live Spectrum page — DONE
4. Start Analysis page + CSV export — DONE
5. Blocker page + JSON persistence — DONE
6. Waterfall, scan-rate readout, Clear button, docs, launch script/desktop shortcut — DONE

**Dependencies:**
- matplotlib, numpy, pytest
- Optional: pyrf24 (for hardware mode)
- Modern Python packaging: pyproject.toml

**Usage:**
```bash
source .venv/bin/activate
export PYTHONPATH="src"
python scripts/run_gui.py
```

---

### Phase 8: v7.1 — Minor Update/Patch (Oct 19, 2026)

v7.1 is a minor update to v7 that maintains the same structure and functionality with minor refinements.

**Same Structure as v7:**
- Identical directory layout
- Same phased development approach
- Same launch scripts and documentation
- Minor bug fixes and stability improvements

**Key Differences:**
- Updated dependencies and minor configuration adjustments
- Same file structure as v7 (docs, scripts, src, tests)
- Maintains backward compatibility with v7 projects

---

### Phase 9: rf_spectrum_visualizer (Main Implementation) (Oct 19, 2026)

The unified main implementation that integrates the best features from all preceding versions into a single, comprehensive application.

**Project Structure:**
```
rf_spectrum_visualizer/
├── main.py                    # Entry point
├── config.py                  # Configuration dataclasses
├── exceptions.py              # Custom exceptions
├── logging_config.py          # JSON Lines logging
├── requirements.txt           # Dependencies
├── HOW_TO_USE_GUIDE.md        # Comprehensive user guide
├── models/                    # Data models
│   ├── channel_record.py      # ChannelObservation, ChannelInfo
│   └── blocklist_model.py     # BlocklistEntry, BlocklistModel
├── services/                  # Shared services
│   ├── data_service.py        # Spectrum data coordination
│   └── persistence_service.py # Configuration persistence
├── radio/                     # Radio backends
│   ├── base_radio.py          # Abstract base class
│   ├── sim_radio.py           # Deterministic simulation
│   └── hardware_radio.py      # pyrf24 hardware interface
├── scanner/                   # Scanning engine
│   ├── scanner_engine.py      # ScannerThread, SpectrumData
│   └── channel_utils.py       # Channel conversion utilities
├── analysis/                  # Channel analysis
│   └── selector.py            # ChannelSelector, recommendations
├── mitigation/                # Channel blocking
│   └── blocklist_manager.py   # JSON blocklist manager
├── exports/                   # Export functionality
│   └── report_generator.py    # ReportGenerator
├── ui/                        # Tkinter UI
│   ├── main_window.py         # Main window with 3 tabs
│   ├── spectrum_page.py       # Spectrum display
│   ├── analysis_page.py       # Analysis & recommendations
│   └── blocker_page.py        # Blocklist management
└── tests/                     # Automated tests
    ├── test_channel_utils.py
    ├── test_blocklist.py
    ├── test_selector.py
    ├── test_scanner.py
    ├── test_exports.py
    └── ...
```

**Key Features (Integrated from all versions):**
- Dual backend (simulation + hardware)
- 126-channel scanning with frequency calculation (2400 + channel MHz)
- Activity percentage calculation: (RPD_positive / valid_samples) × 100
- Three-section architecture: Spectrum, Analysis, Blocker
- Persistent JSON blocklist with atomic writes and corruption recovery
- Channel avoidance algorithm with rankings and recommendations
- Multiple export formats: JSON, CSV, PNG (spectrum/waterfall)
- Comprehensive logging: JSON Lines format for analysis
- Full test suite coverage
- WiFi overlap indicators (channels 1, 6, 11 = nRF 12, 37, 62)
- Simulation scenarios for deterministic testing
- Configuration persistence to config.json

**Configuration Persistence:**
- Settings saved to `rf_spectrum_visualizer/config.json`
- Blocklist saved to `rf_spectrum_visualizer/blocklist.json`
- Logs written to `rf_spectrum_visualizer/logs/countermeasures.jsonl`
- Exports saved to `rf_spectrum_visualizer/exports/`

**Usage:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run with simulation backend (default)
python main.py

# Run with debug logging
python main.py --debug

# Run with hardware backend (requires Raspberry Pi + pyrf24)
python main.py --hardware

# Run with custom configuration
python main.py --config /path/to/custom_config.json
```

**HOW TO USE GUIDE** contains comprehensive documentation covering:
- Project overview and system requirements
- Installation instructions
- UI navigation and keyboard shortcuts
- Spectrum section (channel activity table, live spectrum graph, waterfall display)
- Analysis section (summary cards, channel rankings, recommendations panel)
- Blocker section (blocklist controls, blocked channels table, eligibility preview)
- Hardware setup (Raspberry Pi 3B+ wiring, SPI enable, test hardware)
- Simulation mode (deterministic scenarios, custom scenarios)
- Settings & configuration (thresholds, mitigation, hardware tab)
- Data export (all formats, CSV columns, JSON report structure)
- Automated testing (pytest suite, test categories)
- Troubleshooting (common issues and solutions)
- Limitations & safety (technical limitations, legal compliance)
- Developer guide (architecture overview, adding radio backends, type checks, code style)

---

## 📊 Key Features Across All Versions

| Feature | v1 | v2 | v3 | v3.1 | v5 | v6 | v7 | v7.1 | Main |
|---------|-----|-----|-----|------|-----|-----|-----|------|------|
| 126-Channel Scanning | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| GUI Interface | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| CLI Interface | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| Hardware Mode | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| Simulation Mode | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| Wi-Fi Overlay Markers | | | ✓ | | | ✓ | ✓ | ✓ | ✓ |
| Activity Classification (Clear/Moderate/Busy/Heavy) | | | ✓ | | | ✓ | ✓ | ✓ | ✓ |
| Persistent Blocklist | | | | | | ✓ | ✓ | ✓ | ✓ |
| Channel Avoidance Algorithm | | | | | | ✓ | ✓ | ✓ | ✓ |
| Deterministic Simulation | | | ✓ | | | ✓ | ✓ | ✓ | ✓ |
| Comprehensive Test Suite | | | ✓ | | | ✓ | ✓ | ✓ | ✓ |
| CSV/JSON/PNG Exports | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |
| Anomaly Detection | | | | | ✓ | | | | |
| Channel Classification | | | | | ✓ | | | | |
| Phased Development | | | | | | | ✓ | ✓ | |
| pyproject.toml Packaging | | | | | | | ✓ | ✓ | ✓ |
| Advanced CLI Commands | | | | | | ✓ | | | ✓ |
| Channel Recommendations | | | | | | ✓ | ✓ | ✓ | ✓ |
| Simulation Scenarios | | | | | ✓ | ✓ | ✓ | ✓ | ✓ |
| Blocker Exclusions | | | ✓ | | | | | | |
| Hardware Diagnostics | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 🔧 Dependencies Evolution

### Core Dependencies (stable across all versions):
- `matplotlib>=3.7.0` — Real-time visualization, spectrum graphs, waterfall displays
- `numpy>=1.24.0` — Numerical operations, array handling, EMA calculations
- `pytest>=7.4.0` — Test suite execution and validation
- `pytest-cov>=4.1.0` — Code coverage reporting

### Hardware-Dependent (optional):
- `pyrf24>=1.0.0` — nRF24L01+ Python interface (Raspberry Pi hardware mode)
- `spidev` — SPI device access (Linux Raspberry Pi)

### Version-Specific Additions:

**v2:** Full type hinting support, improved error handling infrastructure

**v3:** 
- Enhanced configuration dataclasses system
- Custom exception hierarchy
- JSON Lines logging format
- Comprehensive test framework

**v5:**
- Advanced anomaly detection capabilities
- Channel classification engine
- Simulation scenario system
- Enhanced report generator

**v6:**
- Persistent JSON blocklist with atomic writes
- Channel avoidance recommendation algorithm
- Comprehensive CLI command structure
- Graceful hardware failure handling

**v7:**
- Modern Python packaging (pyproject.toml)
- Phased development documentation
- Launch scripts and desktop shortcuts
- Venv-aware installation workflow

**Main Implementation:**
- Integrated model-service-architecture
- HOW TO USE GUIDE comprehensive documentation
- Unified project structure consolidating all versions
- Advanced configuration persistence

---

## 🚀 Usage Instructions

### Installation

```bash
# Clone or copy the consolidated project
cd rf_spectrum_visualizer_project_completed

# Install core dependencies
pip install -r requirements.txt

# Optional: For hardware mode (Raspberry Pi + nRF24L01+)
# pip install pyrf24
# Enable SPI: sudo raspi-config → Interface Options → SPI → Enable
```

### Run with Simulation Backend (Default, No Hardware Required)

```bash
# From the project root
python main.py

# Or with debug logging
python main.py --debug

# Run specific scenarios
python main.py --sim
```

### Run with Hardware Backend (Requires Raspberry Pi + nRF24L01+)

```bash
# First time setup:
sudo raspi-config  # Interface Options → SPI → Enable
sudo reboot
sudo usermod -a -G gpio $USER
# Log out and back in for group change to take effect

# Run with hardware backend
python main.py --hardware
```

### CLI Usage Examples

```bash
# Continuous scanning with table output
python main.py

# Single scan and exit
python main.py --sim

# Run deterministic simulation scenario
python main.py --test-scenario mixed --seed 42

# Block a channel (persists across restarts)
python main.py --block 122 --reason "Interference source"

# Get channel recommendations
python main.py --recommend --count 5

# Export scan data
python main.py --export --format json --output my_report.json

# Check hardware availability
python main.py --diagnostic

# Run with custom configuration
python main.py --config my_config.json
```

### GUI Usage

The graphical user interface provides three main tabs:

1. **Spectrum Tab:**
   - Live spectrum bar graph with 126 channels
   - Waterfall display (time vs frequency)
   - Channel activity table with sorting and filtering
   - WiFi channel markers (channels 1, 6, 11)
   - Threshold boundary lines (Clear/Moderate/Busy)

2. **Analysis Tab:**
   - Summary cards (total channels, eligible, blocked, clear, moderate, busy/heavy, insufficient data, sensor errors)
   - Channel rankings table (sorted by activity, lowest first)
   - Recommendations panel (top 10 least-active eligible channels)
   - Blocked channels listed at bottom

3. **Blocker Tab:**
   - Block/unblock channels with reason entry
   - Blocked channels table with timestamps
   - Channel eligibility preview
   - Critical safety notice about software blocking

**Keyboard Shortcuts:**
- `Ctrl+E` — Export all formats
- `Ctrl+J` — Export JSON
- `Ctrl+Shift+C` — Export CSV
- `Ctrl+Q` — Quit application

### Simulation Scenarios

```bash
# Available scenarios (same across v6 and main):
quiet                    # All channels <5% activity
single_busy              # One channel at 80%, rest quiet
spikes                   # Random activity spikes
channel_122_high         # Channel 122 consistently 85%
channel_122_low          # Channel 122 consistently 2%
wifi_like                # WiFi channels 1,6,11 (nRF 12,37,62) active
frequency_hopping        # Hopping pattern on some channels
sensor_errors            # 1% random sensor failures
mixed                    # Realistic mixed environment (default)
burst                    # Burst activity on some channels
high_activity            # All channels 30-50% activity
```

Set simulation seed for reproducible results:
```bash
python main.py --seed 42
# Same seed = identical scan sequences
```

### Configuration

Settings persist to `rf_spectrum_visualizer/config.json`:
- Channel range (default 0-125)
- Scan timing (measurement window, sampling interval)
- Activity thresholds (Clear/Moderate/Busy/Heavy)
- Mitigation parameters (persistent threshold, hysteresis)
- Hardware pins (CE, CSN, SPI speed)
- Simulation seed for reproducibility

---

## 📁 Project Structure

```
rf_spectrum_visualizer_project_completed/
├── README.md                  # This file - comprehensive documentation
├── versions/                  # Empty - historical reference
├── v1/                      # Original version (Oct 14, 2026)
│   ├── app.py                 # Tkinter GUI
│   ├── cli_scan.py            # CLI scanner
│   ├── hardware_radio.py      # nRF24L01+ SPI interface
│   ├── sim_radio.py           # Simulation backend
│   ├── scanner.py             # Spectrum data + scanner
│   ├── mitigation.py          # Active countermeasures
│   ├── config.py              # Configuration dataclasses
│   ├── exceptions.py          # Custom exceptions
│   ├── logging_config.py      # JSON Lines logging
│   ├── requirements.txt       # Dependencies
│   ├── README.md              # Version-specific README
│   └── tools/
│       └── check_pyrf24_api.py  # Hardware diagnostics
├── v2/                      # Modular re-architecture (Oct 15, 2026)
│   └── ... (similar structure with type hints, factory pattern)
├── v3/                      # Dual backend + comprehensive testing (Oct 16, 2026)
│   └── ... (8 test modules, full GUI, exports)
├── v3.1/                    # Blocklist exclusions patch (Oct 17, 2026)
│   └── blocker_exclusions.json
├── v4/                      # ESP32 Random-Channel RF Test Generator (Oct 15, 2026)
│   └── PlatformIO firmware for ESP32 nRF24L01+ test transmitter
├── v4.1/                    # ESP32 v4.1 with modular architecture (Oct 15, 2026)
│   └── PlatformIO firmware updates
├── v5/                      # Anomaly detection + channel classification (Oct 15, 2026)
│   ├── anomaly_detector.py    # Anomaly detection engine
│   ├── channel_classifier.py  # Channel classification & recommendations
│   ├── report_generator.py    # CSV/JSON/JSONL/PNG export
│   └── ... (enhanced config with AnomalyConfig)
├── v6/                      # Production release with blocklist (Oct 17, 2026)
│   ├── persistent blocklist, channel avoidance algorithm
│   ├── comprehensive CLI (50+ commands)
│   ├── Tkinter GUI with blocklist controls
│   └── full test suite
├── v7/                      # Standalone Raspberry Pi visualizer (Oct 17-19, 2026)
│   ├── phased development (6 phases documented in PROGRESS.md)
│   ├── scripts/run_gui.py     # Launch script
│   ├── scripts/check_radio.py # Hardware verification
│   ├── scripts/check_rpd.py   # RPD activity check
│   ├── pyproject.toml         # Modern Python packaging
│   └── docs/PROGRESS.md       # Phase documentation
├── v7.1/                    # Minor update/patch (Oct 19, 2026)
│   └── same structure as v7
├── main/                      # Unified main implementation (Oct 19, 2026)
│   ├── rf_spectrum_visualizer/     # Full Python package
│   │   ├── main.py              # Entry point
│   │   ├── config.py            # Configuration
│   │   ├── models/              # Data models
│   │   ├── radio/               # Radio backends
│   │   ├── scanner/             # Scanning engine
│   │   ├── analysis/            # Channel analysis
│   │   ├── mitigation/          # Channel blocking
│   │   ├── exports/             # Report generation
│   │   ├── services/            # Shared services
│   │   ├── ui/                  # Tkinter UI (3 tabs)
│   │   ├── tests/               # Test suite
│   │   ├── HOW_TO_USE_GUIDE.md  # Comprehensive guide
│   │   ├── requirements.txt     # Dependencies
│   │   └── config.json          # Persistent configuration
│   ├── analysis/                # Channel selector/selector
│   ├── HOW_TO_USE_GUIDE.md    # Integrated user guide
│   └── ...
├── ESP32_RF_Test_V4/            # ESP32 test firmware (Oct 19, 2026)
│   ├── firmware for random-channel RF burst generation
│   ├── PlatformIO project structure
│   ├── nRF24L01+ configuration
│   └── test documentation
├── docs/                      # Consolidated documentation
│   ├── development_history.md   # This chronological overview
│   └── version_comparison.md    # Feature matrix across versions
└── scripts/                   # Utility scripts (inherited from v7)
    ├── run_gui.py               # GUI launch script
    ├── check_radio.py           # Hardware verification
    ├── check_rpd.py             # RPD activity check
    └── rf_spectrum_visualizer.desktop  # Desktop shortcut
```

---

## 🎯 Migration Path

### From v1 → Main
- v1 used `app.py` + `cli_scan.py` directly
- Main integrates these as `main.py` with enhanced configuration
- Dependencies remain similar (matplotlib, numpy)
- Main adds: persistent blocklist, channel avoidance, deterministic simulation

### From v2 → Main
- v2's config.py dataclasses pattern carried forward
- Type hinting infrastructure evolved into main's configuration system
- Factory pattern for radio interfaces evolved into main's radio module system
- Main preserves v2's modular approach but with enhanced features

### From v3 → Main
- v3's dual backend architecture is core to main
- v3's 8-test module suite evolved into main's comprehensive test structure
- Configuration system merged and enhanced
- Main adds: blocklist persistence, channel avoidance, advanced exports

### From v5 → Main
- Anomaly detection concepts integrated into main's analysis module
- Channel classification concepts merged into main's selector
- Simulation scenario system adapted for main's deterministic testing
- Report generation enhanced with additional formats

### From v6 → Main
- Persistent blocklist mechanism directly carried forward
- Channel avoidance algorithm is core feature
- CLI command structure adapted and enhanced
- Test suite patterns merged and expanded
- GUI blocklist controls directly inherited

### From v7 → Main
- Phased development documentation approach
- Launch script and desktop shortcut patterns
- Venv-aware installation workflow
- Modern Python packaging (pyproject.toml concepts)

---

## 📜 License

MIT License - See individual version folders for specific license terms. The consolidated project documentation and organization is provided for educational and diagnostic purposes.

---

## 🙏 Acknowledgments

- Built upon contributions from all project versions (v1 through v7.1)
- nRF24L01+ transceiver communication protocol
- pyrf24 library for Raspberry Pi hardware interface
- matplotlib for real-time visualization
- Python community for test frameworks and best practices
- Raspberry Pi foundation for embedded development platform

---

*Last Updated: October 2026*
*Project: RF Spectrum Visualizer Consolidated Repository*
*Documentation covers development from October 14-19, 2026*