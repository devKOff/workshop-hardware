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

## I²C enablement (Pi)
```bash
sudo raspi-config nonint do_i2c 0
sudo reboot
```

## Verify the INA219 sensor (Pi)
```bash
sudo i2cdetect -y 1
# Look for 0x40 (default INA219 address) or 0x41 (ADDR pin tied to VCC)
```

## Known risks
- PySide6 wheels may be missing on 32-bit Pi OS / Python 3.11+; use apt fallback:
  `sudo apt install python3-pyside6 python3-pyside6.qtwidgets`
- adafruit-circuitpython-ina219 pulls adafruit-blinka; needs I²C enabled.
- 512 MB RAM is tight; keep graph buffers bounded.
- INA219 calibration depends on the shunt resistor on your breakout board.
  The default calibration (shunt=0.1 Ω, max current=1.0 A) may need adjustment
  for your specific board. See docs/HARDWARE.md.

Do not claim Pi compatibility until verified on a real Pi.
