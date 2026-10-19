"""Configuration for the Solar Panel Performance Monitor.

Edit these values to match your actual hardware before running on a Pi.

Hardware-dependent values you MUST verify:
- INA219_ADDRESS : default 0x40 when A0 and A1 are both tied to GND. If your
  breakout uses jumpers/pull-ups, the address may be 0x41–0x47.
- SHUNT_OHMS     : the current-sensing shunt soldered on your INA219 board.
  Commonly 0.1 Ω on Adafruit-style breakouts, but not universal. Measure it or
  read the silkscreen; the current calibration depends directly on it.
- MAX_AMPS       : the largest current you expect to measure. Used to set the
  INA219 gain/calibration. Choose a value comfortably above your expected max
  but not so large that resolution is wasted (e.g., 2.0 A for a small panel).
"""

# I²C
I2C_BUS = 1                    # Raspberry Pi 3 A+ uses I²C bus 1
INA219_ADDRESS = 0x40          # 0x40 when A0=A1=GND; see docs/03_wiring_table.md

# INA219 calibration
SHUNT_OHMS = 0.1               # <-- verify on your actual breakout board
MAX_AMPS = 2.0                 # calibration full-scale current (A)

# Sampling
SAMPLE_INTERVAL_SEC = 1.0      # one sample per second; see docs/06_calculations.md
MAX_GAP_SEC = 86400            # ignore energy integration across gaps > 1 day

# Storage
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "solar.db")
CSV_EXPORT_LIMIT = 100000

# Web
FLASK_HOST = "0.0.0.0"         # listen on all interfaces so phones can reach it
FLASK_PORT = 5000
