# Solar Panel Performance Monitor

A complete, self-contained solar panel performance monitoring system for the
**Raspberry Pi 3 Model A+** with an **INA219** voltage/current/power sensor.
Includes a Flask web dashboard, SQLite persistence, energy integration, CSV/JSON
exports, and a hardware simulator so it can be developed and tested on Windows.

## Features

**Measurements**
- Solar voltage (V), current (mA and A), instantaneous power (W)
- Accumulated energy (Wh) and daily energy generation (Wh/day)
- Timestamp and session duration
- Min / max / average over selected periods
- Sensor connection status and simulation/hardware mode indicator

**Energy calculations**
- Timestamp-based trapezoidal integration of power over elapsed time
- Handles irregular sampling intervals, missing samples, restarts, and local
  midnight rollover correctly
- Energy is recomputed from persisted measurements, so history survives restarts

**Dashboard** (dark blue + solar green, mobile + desktop)
- Live measurement cards and graphs (voltage, current, power)
- Historical energy graph
- Measurement history table with date/time range filters
- CSV and JSON exports
- Loading, empty-data, disconnected-sensor, and error states
- Polling updates — no full page refresh

**Backend**
- Hardware abstraction for the INA219 + simulated sensor for Windows
- Configurable sampling interval (default 2 seconds)
- Documented JSON API with input validation and consistent errors
- SQLite protection against concurrent access; duplicate-sampler prevention
- Graceful shutdown; timestamped logging

## Project structure

```
solar-panel-monitor/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── .env.example
├── config.example.json
├── run.py
├── app/                 # Flask application
│   ├── __init__.py      # application factory (create_app)
│   ├── config.py        # configuration loading & validation
│   ├── models.py        # data models
│   ├── database.py      # SQLite persistence (thread-safe)
│   ├── routes.py        # web page routes
│   ├── api.py           # JSON API routes
│   ├── services/        # sensor, energy, history services
│   └── hardware/        # INA219 driver + simulated sensor
├── scripts/             # Pi setup, start, stop, hardware check
├── tests/               # pytest suite (hardware-independent)
└── docs/                # wiring, install, test plan, troubleshooting
```

## Technology stack

- Python 3, Flask 3.1.3
- SQLite (built-in)
- HTML5, CSS3, JavaScript, Chart.js 4.4.1 (vendored for offline use)
- pytest, pytest-mock, pytest-cov
- `ina219` library on the Raspberry Pi (hardware mode only)

No Docker, cloud databases, paid APIs, or unnecessary frameworks.

## Quick start — Windows (simulation mode)

No hardware needed. The simulated sensor generates realistic solar readings.

```powershell
# clone the repo
git clone <YOUR_GITHUB_REPO_URL>
cd solar-panel-monitor

# virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# configure (templates copied; edit if desired)
copy .env.example .env
copy config.example.json config.json

# run
python run.py
```

Open **http://localhost:5000/**.

Run the tests:

```powershell
python -m pytest
```

## Quick start — Raspberry Pi (hardware mode)

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd solar-panel-monitor

bash scripts/setup_pi.sh
sudo reboot                         # enable I²C

# wire the INA219 per docs/HARDWARE_WIRING.md (POWER OFF first), then:
sudo i2cdetect -y 1                 # confirm the INA219 address
. .venv/bin/activate
python scripts/check_hardware.py    # confirm a reading

cp .env.example .env                # set SENSOR_MODE=hardware, I2C address, etc.
./scripts/start.sh
```

Open **http://<PI-IP-ADDRESS>:5000/** from any device on the same Wi-Fi.

See `docs/INSTALL_RASPBERRY_PI.md` for optional systemd auto-start and LAN
access instructions. See `docs/HARDWARE_WIRING.md` for the safe wiring
procedure and multimeter checklist.

## Configuration

Configuration is resolved in this priority order (highest first):
1. Environment variables (`SENSOR_MODE=...`, etc.)
2. `config.json` (create from `config.example.json`)
3. `.env` (create from `.env.example`)
4. Built-in defaults

Key options:

| Setting | Default | Meaning |
|---------|---------|---------|
| `SENSOR_MODE` | `simulation` | `simulation` or `hardware` |
| `SAMPLING_INTERVAL_SECONDS` | `2` | Seconds between samples |
| `INA219_I2C_ADDRESS` | `0x40` | I²C address (verify with `i2cdetect`) |
| `INA219_SHUNT_OHMS` | `0.1` | Shunt resistor value (verify your breakout) |
| `INA219_MAX_EXPECTED_AMPS` | `0.5` | Max expected current |
| `DATABASE_PATH` | `solar_monitor.db` | SQLite file |
| `HOST` | `0.0.0.0` | Bind address (0.0.0.0 = LAN access) |
| `PORT` | `5000` | HTTP port |
| `DEBUG` | `false` | Flask debug mode |

Never commit `.env` or `config.json` — both are gitignored.

## JSON API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Service + sensor health |
| `/api/measurements/current` | GET | Latest reading |
| `/api/measurements/history` | GET | Filtered history (`?start=&end=&limit=`) |
| `/api/energy/summary` | GET | Aggregated energy over a period |
| `/api/energy/daily` | GET | Per-day energy (`?start_date=&end_date=`) |
| `/api/export/csv` | GET | CSV export of measurements |
| `/api/export/json` | GET | JSON export of measurements |
| `/api/sampling/start` | POST | Start background sampler |
| `/api/sampling/stop` | POST | Stop background sampler |
| `/api/sampling/status` | GET | Sampler status |

All errors return `{"error": ..., "message": ...}` with an appropriate HTTP status code.

## Testing

All tests use mocked hardware and run on Windows without a sensor:

```powershell
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
```

INA219 hardware tests are skipped on Windows and run on the Pi during physical
validation. See `docs/TEST_PLAN.md`.

## GitHub deployment (Windows)

```powershell
git init
git add .
git commit -m "Initial commit"
git remote add origin <YOUR_GITHUB_REPO_URL>
git branch -M main
git push -u origin main
```

Do not overwrite an existing remote without checking `git remote -v` first.
`.env`, `config.json`, `*.db`, `.venv/`, `logs/`, and `__pycache__/` are
excluded from Git.

## Physical hardware status

Physical INA219 testing on the Raspberry Pi is **pending** — it requires the
actual Pi 3 Model A+, INA219, 6 V solar panel, and 33 Ω resistor. It will be
marked passed, failed, or pending based on measured results (see
`docs/TEST_PLAN.md`, section "Physical hardware tests").

## License

MIT License. See `LICENSE`.
