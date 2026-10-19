# Pi Compatibility

Target: Raspberry Pi 3 Model A+ (512 MB RAM), Raspberry Pi OS (32/64-bit).

## Verified
- None yet. Plan only, not a verification.

## Install (documented, not verified on hardware)
```bash
git clone <url> solar_pi_project_v4
cd solar_pi_project_v4
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-pi.txt
python main.py
```

## Known risks
- PySide6 wheels may be missing on 32-bit Pi OS / Python 3.11+; use apt fallback.
- adafruit-circuitpython-ina219 pulls adafruit-blinka; needs I²C enabled.
- 512 MB RAM is tight; keep graph buffers bounded.

Do not claim Pi compatibility until verified on a real Pi.