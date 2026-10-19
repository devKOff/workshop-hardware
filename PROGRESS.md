# Progress — Solar Panel Performance Monitor

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
