# Testing procedure and troubleshooting

## Test plan

| # | Step | What to verify | Pass criterion |
|---|------|----------------|----------------|
| 1 | Pi power & I²C config | Pi boots; `/dev/i2c-1` exists; `dtparam=i2c_arm=on` set | I²C device node present |
| 2 | Detect INA219 | `sudo i2cdetect -y 1` shows the sensor | Address 0x40 (or your configured address) appears |
| 3 | Voltage & current | Run manual sensor test; panel in light, load connected | Nonzero plausible voltage (~panel Voc under load), current > 0 |
| 4 | Multimeter comparison | Multimeter voltage across panel; current in series | Within ~5–10% of dashboard (INA219 + shunt tolerance) |
| 5 | Different lighting | Cover panel / use lamp / move to bright sun | Readings rise and fall with light level |
| 6 | Power & energy plausibility | P = V × I; energy accumulates over time | Energy increases only when power > 0; P matches V×I |
| 7 | Database & CSV | Readings appear in SQLite; CSV download works | Rows inserted; CSV file opens with correct columns |
| 8 | Dashboard & graphs | Browser shows values; charts update | Values match latest DB row; charts render |
| 9 | Restart / disconnect recovery | Unplug sensor briefly, then reconnect; restart app | Dashboard shows error during disconnect, recovers after; cumulative energy preserved across restart |

## Troubleshooting guide

### INA219 not detected on I²C bus
- **Cause:** Wiring wrong, I²C not enabled, sensor unpowered, wrong address.
- **Fix:**
  1. Confirm `sudo i2cdetect -y 1` runs (I²C enabled; reboot if you just enabled it).
  2. Check VCC → Pi pin 1 (3.3 V), GND → pin 6, SDA → pin 3, SCL → pin 5.
  3. Check A0/A1 strapping; if your board responds at a different address, update
     `INA219_ADDRESS` in `src/config.py`.
  4. Measure VCC on the breakout with a multimeter (should be ~3.3 V).

### Incorrect or zero readings
- **Cause:** Panel not in light, load not connected, reversed polarity, shunt value mismatch.
- **Fix:**
  1. Ensure the panel is illuminated and the 22 Ω load is connected across VIN− → panel −.
  2. Confirm panel + → VIN+, panel − → load → VIN− (not reversed).
  3. Verify `SHUNT_OHMS` in `src/config.py` matches your board's actual shunt.
  4. Compare with a multimeter; if the INA219 reads 0 but the multimeter shows
     voltage/current, the I²C or shunt path is faulty.

### Reversed current direction (negative current)
- **Cause:** Panel polarity swapped relative to VIN+/VIN−.
- **Fix:** The INA219 supports bidirectional current and correctly reports the
  sign. To make current positive again, swap panel + and panel − so current
  flows VIN+ → VIN−. Negative current is not an error — it indicates direction.

### Negative power readings
- **Cause:** Negative current × positive voltage = negative power (reverse flow),
  or a range/calibration issue.
- **Fix:** The code only integrates **positive** power into energy, so reverse
  flow never subtracts from generated energy. If you expect only forward flow,
  check wiring polarity.

### Implausible voltage measurements
- **Cause:** Panel Voc above breakout rating, floating VIN+, or wrong reference.
- **Fix:** Measure panel Voc with a multimeter. Confirm it is below the
  breakout's bus-voltage limit (typically 26 V). Confirm VIN+ is connected to
  panel + and not floating.

### Database errors
- **Cause:** Permissions, missing `data/` folder, locked database.
- **Fix:** The app creates `data/solar.db` automatically. Ensure the Pi user can
  write to the project folder. If a concurrent writer locks the DB, the code's
  30 s timeout and threading lock should handle it; check `journalctl` or the
  console traceback for the exact SQLite error.

### Dashboard not accessible from another device
- **Cause:** Flask bound to localhost, wrong IP, firewall, device on different
  network.
- **Fix:**
  1. The app runs on `0.0.0.0` (all interfaces) — confirm `FLASK_HOST = "0.0.0.0"` in `src/config.py`.
  2. Use the Pi's actual LAN IP (`hostname -I`), not `localhost`/`127.0.0.1`, from the phone.
  3. Phone and Pi must be on the same Wi-Fi/LAN.
  4. Try `curl http://<pi-ip>:5000/api/current` from the Pi to confirm the server responds.
