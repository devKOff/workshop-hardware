# How to Use

## First run (Windows)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python main.py
```

## Simulation mode (default on Windows)
No hardware needed. Every reading labeled `sensor_mode = "simulated"`.

## Hardware mode (Pi)
Connect INA219 per docs/HARDWARE.md. Enable I²C (`sudo raspi-config`). Install
`requirements-pi.txt`. Switch to hardware mode in Settings.

## Pages
Dashboard, Live Monitoring, Historical Data, CSV Reports, Settings, System Info.

## Data & settings
SQLite DB (WAL mode). Exports UTF-8 with BOM, temp+atomic rename. Backups never
overwrite silently.