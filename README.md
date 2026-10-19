# Solar Panel Performance Monitor

Offline native desktop app that reads voltage/current/power from an INA219 on a
Raspberry Pi 3 Model A+, then shows, stores and exports solar-panel performance.
Developed on Windows in simulation mode, pushed to GitHub, then deployed on the Pi.

No website, web server, cloud, remote API or accounts. Internet only for
installing dependencies or cloning the repo.

## Quick start (Windows, simulation mode)
```powershell
cd solar_pi_project_v4
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python main.py --version
python main.py
```

## Testing
```powershell
pytest -q
```