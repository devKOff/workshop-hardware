# Release Checklist — Solar Panel Performance Monitor v1.0.0-dev

## Verified features (tested on Windows, simulation mode)

| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| 1 | Native PySide6 desktop GUI | Verified | 6-page window launches, resizable, dark title bar |
| 2 | Dark charcoal title bar "Solar Panel Performance Monitor" | Verified | Windows immersive dark mode |
| 3 | Navy-and-green accent theme, white workspace | Verified | stylesheet applied |
| 4 | Left sidebar with 6 vertical navigation items | Verified | Dashboard, Live Monitoring, Historical Data, CSV Reports, Settings, System Information |
| 5 | Bottom-left APP OPTIONS button | Verified | Present in navigation footer |
| 6 | Bottom-right context-sensitive action button | Verified | "Start monitoring" / "Export CSV…" |
| 7 | Dashboard: live V/A/W/Wh + status + summary | Verified | Metric cards update via engine callback |
| 8 | Live Monitoring: Start/Stop/Pause/Resume/Clear + interval | Verified | Engine lifecycle tested |
| 9 | Live graphs: bounded data buffers | Verified | pyqtgraph PlotWidget, time-window cutoff |
| 10 | Historical Data: sortable SQLite table + date filter | Verified | DAO list_measurements + GUI table |
| 11 | CSV Reports: fixed schema, UTF-8+BOM, atomic rename | Verified | CSV_COLUMNS, export_measurements, error handling |
| 12 | Settings: interval + mode, persisted across restart | Verified | SettingsService + Settings page |
| 13 | System Information: versions, OS, backend, DB health, diagnostics | Verified | All labels present |
| 14 | Simulation mode (Windows, no hardware) | Verified | Realistic sunlight/clouds/noise/faults |
| 15 | P = V × I consistent power calculation | Verified | compute_power / attach_power tested |
| 16 | Trapezoidal energy integration | Verified | EnergyIntegrator with known sequences |
| 17 | Invalid readings never accumulated as energy | Verified | Chain broken on fault/NaN |
| 18 | Hardware mode never silently substitutes simulation | Verified | BackendError raised, mode stays "hardware" |
| 19 | SQLite persistent storage (WAL, app-data dir) | Verified | default_db_path not in CWD |
| 20 | Records persist across application restarts | Verified | Re-open same DB file test |
| 21 | Settings validation rejects invalid input | Verified | SettingsError on negative/zero/non-numeric/unknown |
| 22 | One acquisition worker max, no duplicate workers | Verified | start() no-op when running/paused |
| 23 | Thread safety, worker cleanup on shutdown | Verified | worker.join(timeout=10.0) |
| 24 | Windows unaffected by Pi dependencies | Verified | Lazy adafruit_ina219 import, no Pi imports in core/simulation |

## Pending hardware tests (require Raspberry Pi 3 Model A+ + INA219)

| # | Hardware test | Status | Notes |
|---|---------------|--------|-------|
| H1 | Genuine INA219 readings over I²C | Pending | No Pi available on Windows dev machine |
| H2 | INA219 initialization failure handling | Pending | Mock-tested only |
| H3 | Sensor disconnection mid-run | Pending | Mock-tested only |
| H4 | Hardware mode never silently falls back to simulation | Pending | Code guard in place, untested on real Pi |
| H5 | Calibration verification (shunt resistor, max current) | Pending | Default 0.1 Ω / 1.0 A may need adjustment |
| H6 | Separate regulated 5 V Pi supply + panel wiring | Pending | Physical wiring, not testable on Windows |

## Git / GitHub release status

| Item | Status |
|------|--------|
| All 12 phases committed | Complete (phase-1-complete … phase-11-complete) |
| All 12 phases tagged | Complete |
| Working tree clean | Verified |
| `git diff --check` clean | Verified |
| Remote configured | Not configured (no origin) |
| Pushed to GitHub | Pending — awaiting GitHub URL |

## Raspberry Pi deployment prerequisites

- Raspberry Pi 3 Model A+ with Raspberry Pi OS (32/64-bit)
- INA219 wired to I²C bus 1 (address 0x40 or 0x41)
- 6 V, 3 W solar panel + 33 Ω resistive load
- Separate regulated 5 V supply for the Pi
- I²C enabled (`sudo raspi-config nonint do_i2c 0`)
- Python 3.10+, pip, git

## Commands for Pi deployment (exact)

```bash
# Clone (replace <url> with GitHub URL)
git clone <url> solar_pi_project_v4
cd solar_pi_project_v4

# Install dependencies
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-pi.txt

# Enable I²C and reboot
sudo raspi-config nonint do_i2c 0
sudo reboot

# Verify sensor detection
sudo i2cdetect -y 1

# Launch (simulation mode first, then switch to Hardware in Settings)
python main.py
```
