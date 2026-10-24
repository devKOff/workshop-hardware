# How to Use the Solar Panel Performance Monitor

## Launching

On Windows (development, simulation mode):

```powershell
.venv\Scripts\Activate.ps1
python main.py
```

On the Raspberry Pi 3 Model A+ (hardware mode), see `docs/` for the full
deployment procedure, including enabling I²C and verifying the INA219 sensor.

## The six sections

Use the left sidebar to navigate between the six sections:

1. **Dashboard** — live voltage (V), current (A), power (W), accumulated energy
   (Wh), measurement status, active backend, and sensor connection status.
   Simulated readings are clearly labeled as such.
2. **Live Monitoring** — real-time voltage/current/power graphs with Start,
   Stop, Pause, Resume, and Clear controls, plus a configurable sampling
   interval.
3. **Historical Data** — sortable table of saved measurements with date/time
   filtering, retrieved from SQLite. Records persist across restarts.
4. **CSV Reports** — export historical measurements to a user-selected CSV file
   with a fixed, documented column schema. Shows progress and success/error
   messages.
5. **Settings** — configure the sampling interval and operating mode
   (Simulation on Windows, Hardware on Raspberry Pi). Settings persist across
   restarts. Invalid input is rejected with an explanation.
6. **System Information** — application/Python versions, OS, backend status,
   database health, sensor diagnostics, errors, and recent logs.

## Mode selection

Open **Settings** and choose the operating mode:

- **Simulation Mode** (default on Windows): realistic simulated sunlight,
  irradiance, cloud, and noise. All data is labeled `simulated`. Safe to use
  without any hardware.
- **Hardware Mode** (Raspberry Pi): reads the genuine INA219 sensor over I²C.
  Never select hardware mode on a machine without the INA219 connected — doing
  so produces an error state, not simulated data.

Settings are saved automatically and restored on the next launch.

## Measurements and energy

Power is calculated consistently as `P = V × I`. Accumulated energy uses
trapezoidal integration over actual elapsed time. Invalid readings are never
accumulated and never cached as new values.

## CSV export

Choose **CSV Reports**, select a destination file, and export. The export uses a
fixed column schema with consistent units (V, A, W, Wh) and ISO-8601 timestamps.
Empty datasets, invalid paths, and permission errors are reported honestly.

## Troubleshooting

- App will not launch: ensure PySide6 is installed (`pip install -r requirements.txt`).
- No sensor readings: check Settings mode and, on the Pi, that I²C is enabled and
  the INA219 is wired and detected (`i2cdetect -y 1`).
- Missing data: confirm the database is writable (stored in the application-data
  directory) and check System Information for database health.
