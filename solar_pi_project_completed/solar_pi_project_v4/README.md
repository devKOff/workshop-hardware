# Solar Panel Performance Monitor

Native offline desktop application (PySide6) that measures, logs, and reports
solar-panel performance. Developed on Windows in simulation mode and deployed
to a Raspberry Pi 3 Model A+ with an INA219 voltage/current sensor.

No website, no web server, no cloud, no accounts.

## Hardware target

- Raspberry Pi 3 Model A+
- INA219 voltage/current sensor over I²C
- 6 V, 3 W solar panel
- 33 Ω resistive load
- Separate regulated 5 V supply for the Raspberry Pi

## Repository layout

```
pyproject.toml            # project metadata and packaging
requirements.txt          # Windows runtime deps (PySide6, optional pyqtgraph)
requirements-dev.txt      # test deps (pytest, pytest-qt)
requirements-pi.txt       # Pi runtime deps (INA219 driver; PySide6 via apt)
.gitignore                # ignore venv, caches, db, csv, logs
README.md                 # this file
HOW_TO_USE_GUIDE.md       # end-user usage guide
TODO.md                   # phase plan and pending work
main.py                   # application entry point
config/                   # application constants and defaults
database/                 # SQLite schema, connection, DAO, settings (preserved)
measurement/              # measurement model, power, validation, energy (preserved)
sensor/                   # sensor interface + simulation backend (preserved)
src/solar_monitor/gui/    # PySide6 main window, navigation, six pages, widgets, theme
scripts/                  # Pi deployment helpers
tests/                    # pytest + pytest-qt suite
docs/                     # installation, wiring, troubleshooting, test reports
data/                     # application data directory (production database)
logs/                     # application logs
exports/                  # CSV export destination
```

## Windows development

```powershell
# inside solar_pi_project_v4/
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
# run the test suite
pytest tests/
# launch the GUI (simulation mode on Windows)
python main.py
```

## Raspberry Pi 3 Model A+ deployment

See `docs/` for installation, I²C enablement, sensor verification, wiring, and
the exact commands for cloning, installing dependencies, selecting hardware
mode, and launching the application.

## Mode

Simulation vs hardware mode is chosen explicitly by the user (Settings page) and
shown in the header. Windows runs in simulation mode without the INA219 driver.
Hardware failure is shown as an honest error state — simulated or stale readings
are never substituted.

## License

Private / internal use.
