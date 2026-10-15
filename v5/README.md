# RF Spectrum Visualizer V5

2.4 GHz ISM band monitor using nRF24L01+ transceiver on Raspberry Pi.

## Quick Start

### Installation
```bash
cd v5
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run GUI (Simulation Mode)
```bash
python app.py --sim
```

### Run CLI Scanner
```bash
# Continuous table display (simulation)
python cli_scan.py --backend sim --format table

# Single scan with JSON output
python cli_scan.py --backend sim --single-scan --format json

# Hardware mode (requires Raspberry Pi + nRF24L01+)
python cli_scan.py --backend hardware --single-scan
```

### Run Tests
```bash
pytest tests/ -v
```

### Hardware Diagnostic
```bash
python tools/check_pyrf24_api.py --init
```

## Configuration

All settings in `config.py`:
- `ChannelConfig` - scan range (0-125), channel filters
- `ScanConfig` - measurement window, sampling interval, min samples
- `ThresholdConfig` - CLEAR/MODERATE/BUSY/HEAVY LOAD boundaries
- `AnomalyConfig` - detection thresholds for anomalies
- `SimulationConfig` - scenario selection for testing

## Simulation Scenarios

```bash
# Test specific scenarios
python cli_scan.py --test-scenario persistent_busy
python cli_scan.py --test-scenario sudden_spike
python cli_scan.py --test-scenario hopping_like

# List all scenarios
python -c "from sim_radio import SimRadio; print(SimRadio.get_available_scenarios())"
```

## Output Formats

- **table** - Live updating terminal table (default)
- **ascii** - ASCII-only table
- **json** - JSON Lines streaming
- **csv** - CSV export

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Tkinter GUI with spectrum graph, waterfall, channel table |
| `cli_scan.py` | Command-line scanner with filtering/sorting |
| `scanner.py` | Background scanner thread, SpectrumData storage |
| `sim_radio.py` | Deterministic simulation backend |
| `hardware_radio.py` | pyrf24 hardware interface |
| `anomaly_detector.py` | Anomaly detection engine |
| `channel_classifier.py` | Activity classification & recommendations |
| `mitigation.py` | Alerting & safe channel recommendations |
| `report_generator.py` | CSV/JSON/JSONL/PNG export |
| `config.py` | Validated configuration system |

## Hardware Requirements

- Raspberry Pi 3B+ (or compatible)
- nRF24L01+ module
- SPI enabled (`sudo raspi-config`)
- Wiring: CE=GPIO25, CSN=CE0, SCK=GPIO11, MOSI=GPIO10, MISO=GPIO9, VCC=3.3V, GND=GND

## Limitations

- nRF24L01+ provides binary energy detection (RPD), not calibrated RSSI
- Activity % = positive RPD samples / total valid samples
- Cannot identify protocols or specific transmitters
- Results are heuristic classifications, not standardized measurements