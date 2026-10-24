# Installation — Windows (simulation / development mode)

The Windows laptop runs the monitor in **simulation mode**: a software model of
the INA219 generates realistic solar readings. No hardware is required. This is
the environment for writing code, running tests, and pushing to GitHub.

## Prerequisites

- Python 3.10 or later (tested with Python 3.12)
- Git

## 1. Clone the repository

```powershell
git clone <YOUR_GITHUB_REPO_URL>
cd solar-panel-monitor
```

## 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure

Copy the templates and edit as needed:

```powershell
copy .env.example .env
copy config.example.json config.json
```

The default `SENSOR_MODE=simulation` means no hardware is needed. Leave
`INA219_I2C_ADDRESS`, shunt, and amp settings at their defaults; they only
apply to hardware mode.

## 5. Run

```powershell
python run.py
```

Open the dashboard at **http://localhost:5000/** (or http://127.0.0.1:5000/).

## 6. Run the test suite

```powershell
python -m pytest
```

Coverage report:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

The INA219 hardware tests are skipped automatically on Windows because the
`ina219` library (and its `smbus` dependency) is Linux/Raspberry Pi only.

## Notes

- The simulated sensor produces a day/night curve, so readings vary with the
  system clock. Power will be near zero at "night" in the simulation.
- Do not commit `.env` or `config.json` — they are gitignored.
