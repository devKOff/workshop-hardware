# Progress — Solar Panel Performance Monitor

## Existing project findings (monitor_gui task)

- Project root: `solar_pi_project_v4/` (git root, branch `master`, origin `https://github.com/devKOff/workshop-hardware.git`).
- Existing app: PySide6 + pyqtgraph multi-page GUI under `src/solar_monitor/`; this task adds a NEW standalone single-window `monitor_gui/` package using **Tkinter + Matplotlib** as prescribed by the task spec (v4's PySide6 app is a separate multi-page application; this monitor reuses only the sensor backend). Written reason recorded in PROGRESS.md Phase 1.
- I²C bus: `1`; INA219 address: `0x40` (ADDR pin to GND; `0x41` if tied to VCC).
- INA219 library: `adafruit-circuitpython-ina219`, imported **lazily** (only in `src/solar_monitor/backends/hardware.py`), so Windows runs without it.
- Wiring (high-side): solar panel + → INA219 Vin+; panel − / one end of 33 Ω load → INA219 Vin−; other end of load → GND. Panel powered separately; Pi on separate regulated 5 V.
- Shunt: `0.1 Ω`; max current: `1.0 A`; Current_LSB ≈ 30.5 µA (docs/HARDWARE.md).
- Reusable existing modules (NOT modified): `solar_monitor.backends.hardware.INA219HardwareBackend`, `solar_monitor.backends.simulation.SimulatedSensor`, `solar_monitor.backends.interface.{SensorBackend,SensorReading,BackendError}`.
- Existing `core/` helpers available: `power.compute_power` (V×I primary, register within 10%), `validation` limits (30 V / 10 A / 60 W), `energy.EnergyIntegrator` (trapezoidal, 5× interval max gap).
- `.gitignore` already excludes `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.csv`, `*.log`; will add `solar_10min_report_*.txt`.

## Roadmap (this task)
- [x] Phase 1: Core — config, sensor interface, simulator, INA219 wrapper, detection, sample model & validation
- [ ] Phase 2: Logic — sampler/worker, analysis & energy
- [ ] Phase 3: GUI + export — window, countdown, live readings, charts, CSV & report export
- [ ] Phase 4: Hardening + docs — README, error handling, shutdown, full test run

## Status

Phase 1 complete (commit 052b064, pushed to origin/master).

### Phase 1 report — sensor layer and validation
- Files created: `monitor_gui/__init__.py`, `monitor_gui/config.py`, `monitor_gui/sample.py`, `monitor_gui/sensor.py`, `tests/test_monitor_gui_sample.py`, `tests/test_monitor_gui_sensor.py`.
- Files modified: `PROGRESS.md`, `.gitignore` (added `solar_10min_report_*.txt`).
- Commands run: `python -m compileall -q monitor_gui tests` (clean); `python -m pytest -q tests/test_monitor_gui_sample.py tests/test_monitor_gui_sensor.py -p no:cacheprovider` → **17 passed, 0 failed**. Full repo suite: 5 pre-existing failures in v4 GUI tests (`test_gui_pages.py`, `test_settings_persistence.py` — `SettingsPage.probe()`/`mode_combo` bugs, unrelated to this task, in files not touched). `ruff`/`pyflakes` not installed (not added per rules).
- Commit: `052b064 feat: sensor layer and validation`; `git status` clean; `git push origin master` succeeded.
- Known limitations: real INA219 hardware not present on Windows (hardware path correctly reports unavailable → `read_error`); overflow flag read best-effort via the library sensor's public `overflow` attribute; 10-minute hardware run not verified (to be run on the Pi).
- Next step: Phase 2 — sampler/worker (10-minute run, auto-stop, early stop), analysis and energy.

## Roadmap (12 phases, all complete)

### Part 1 — Foundation, core logic, storage
- [x] Phase 1: Project structure and GUI foundation
- [x] Phase 2: Core logic and measurement models
- [x] Phase 3: SQLite database and persistence

### Part 2 — GUI, monitoring, history and reports
- [x] Phase 4: Simulation backend
- [x] Phase 5: Measurement engine and energy tracking
- [x] Phase 6: Complete six-page GUI
- [x] Phase 7: Live graphs and dashboard integration
- [x] Phase 8: Historical data and CSV reports

### Part 3 — Hardware, testing, deployment
- [x] Phase 9: Settings and system diagnostics
- [x] Phase 10: Real INA219 hardware integration (mock-tested on Windows)
- [x] Phase 11: Full testing, regression fixes, and final audit
- [x] Phase 12: Documentation, GitHub release, and Raspberry Pi deployment

## Status

All 12 phases complete. Test suite: 146 passed, 1 skipped, 0 failed.
Working tree: clean. Tags: phase-1-complete ... phase-11-complete.
Push to GitHub: pending (no origin remote configured — awaiting GitHub URL).

## Raspberry Pi 3 Model A+ deployment commands

```bash
# 1. Clone the repo (replace <url> with the actual GitHub URL)
git clone <url> solar_pi_project_v4
cd solar_pi_project_v4

# 2. Create venv and install dependencies
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-pi.txt

# 3. Enable I²C
sudo raspi-config nonint do_i2c 0
sudo reboot

# 4. Verify the INA219 sensor is detected on I²C bus 1
sudo i2cdetect -y 1
# Look for 0x40 (ADDR pin to GND) or 0x41 (ADDR pin to VCC)

# 5. Launch the application (simulation mode by default)
python main.py

# 6. Select Hardware mode in Settings → Operating mode → Hardware → Save
#    (only after confirming the INA219 is detected via i2cdetect)
```
