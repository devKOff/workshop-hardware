# Troubleshooting Guide — Solar Panel Performance Monitor

## App will not launch

**Symptom:** `python main.py` produces an error or no window appears.

**Possible causes & fixes:**
- PySide6 not installed: `pip install -r requirements.txt -r requirements-dev.txt`
- Running from wrong directory: run inside `solar_pi_project_v4/`
- Missing Qt platform plugin: set `$env:QT_QPA_PLATFORM="offscreen"` (headless/CI) or unset it (normal desktop)

## No sensor readings / "Sensor: unavailable"

**Simulation mode (Windows default):**
- Confirm Settings → Operating mode is "Simulation"
- Simulated data is labeled `sensor_mode = "simulated"` — expected on Windows

**Hardware mode (Raspberry Pi):**
- Confirm I²C is enabled: `sudo raspi-config nonint do_i2c 0` then reboot
- Verify sensor detection: `sudo i2cdetect -y 1` → look for `0x40` or `0x41`
- Check wiring per `docs/HARDWARE.md` (INA219 VCC→3.3V, GND→GND, SCL→GPIO3, SDA→GPIO2)
- Confirm separate regulated 5 V supply for the Pi (not from the solar panel)
- Check System Information page for "Init error" details

## Hardware mode silently shows simulation data

This should never happen. If it does:
- Confirm you explicitly selected "Hardware" in Settings and clicked Save
- Check System Information → Backend diagnostics → `available: yes`
- If hardware is unavailable, the app shows an error state — it does not fall back to simulation

## CSV export fails

- **Permission denied:** run as a user with write access to the destination folder
- **Invalid path:** choose a valid destination; the app creates parent directories automatically
- **No measurements to export:** take some measurements first (Start monitoring in simulation mode)

## Database is locked / corrupted

- The app uses SQLite WAL mode with `synchronous=NORMAL`
- Do not copy or move `solar_measurements.db` while the app is running
- Use `database.backup.backup()` / `restore()` for safe backups (never overwrites silently)
- The database lives in the user application-data directory (%APPDATA% on Windows), not the working directory

## INA219 reads near-zero voltage/current

- Confirm the solar panel is connected and illuminated
- Verify wiring per `docs/HARDWARE.md`
- Check calibration: shunt resistor and max current must match your breakout board
  (default: shunt=0.1 Ω, max current=1.0 A — adjust in `src/solar_monitor/backends/hardware.py`)
- Confirm the INA219 is detected: `sudo i2cdetect -y 1`

## Where is my data stored?

- Windows: `%APPDATA%\Solar Panel Performance Monitor\solar_measurements.db`
- Linux: `~/.local/share/Solar Panel Performance Monitor\solar_measurements.db`
- This is the user-writable application-data directory — not the working directory

## Getting help

Check `docs/System Information` in the app for backend diagnostics, dependency status, and init errors. The `TEST_REPORT.md` documents the full automated test results.
