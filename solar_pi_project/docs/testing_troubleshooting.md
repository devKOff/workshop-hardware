# Solar Panel Performance Monitor - Testing and Troubleshooting

This section provides a systematic test plan and troubleshooting guide for the
Solar Panel Performance Monitor project.

## Test Plan

### 1. Verify Raspberry Pi Power and I²C Configuration

**Goal:** Ensure the Pi is powered correctly and I²C is enabled.

**Steps:**
1. Power the Raspberry Pi using the 5 V micro-USB power supply.
2. Check the Pi boots successfully (LED indicators, HDMI output, or network connectivity).
3. Open a terminal and verify I²C is enabled:

```bash
i2cdetect -y 1
```

   - You should see an I²C scanner grid (16×16 or 8×8 address matrix).
   - If no grid appears, or if you get an error like "Error: Cannot open /dev/i2c-1",
     I²C may not be enabled.

**Troubleshooting:**
- Re-run `raspi-config` → Interface Options → I²C → Yes.
- Reboot the Pi after enabling I²C.
- Verify the power supply provides stable 5 V (undervoltage can disable peripherals).
- Check that the microSD card is properly seated and Raspberry Pi OS is correctly installed.

### 2. Detect the INA219 on the I²C Bus

**Goal:** Confirm the INA219 module is visible on the I²C bus.

**Steps:**
1. With the INA219 wired to the Pi (VCC to pin 1, GND to pin 6, SDA to pin 3, SCL to pin 5),
   run:

```bash
i2cdetect -y 1
```

2. Look for the INA219 address in the output. The default address is **0x40** (when A0 and A1 are floated).
3. If you see `40` in the output, the module is detected.

**Troubleshooting - INA219 Not Detected:**

| Possible Cause | Solution |
|----------------|----------|
| Wrong I²C address | Check A0/A1 pin connections. Connect A0 or A1 to 3.3 V or GND to change the address, then re-scan. |
| I²C not enabled | Re-enable I²C via `raspi-config` and reboot. |
| Wrong wiring | Verify: VCC→pin1, GND→pin6, SDA→pin3, SCL→pin5. Use a multimeter to continuity-test each wire. |
| Module damaged | Try a different INA219 module if available. |
| Pull-up resistors missing | Most INA219 breakout boards have built-in pull-ups, but verify. |
| No 3.3 V on VCC | Confirm Pi is powered; VCC should read ~3.3 V. |

### 3. Test Voltage and Current Measurements

**Goal:** Verify the INA219 reads reasonable voltage and current values.

**Steps:**
1. Ensure the virtual environment is active and the sensor library is installed.
2. Run the test script:

```bash
source .venv/bin/activate
python3 src/sensor_reader.py test
```

3. Observe the readings. With no load (panel open-circuit), you should see:
   - Voltage: ~7–9 V (depending on panel and sunlight)
   - Current: ~0 mA (no load)
4. Connect the 22 Ω / 5 W test load across the panel.
5. Readings should now show:
   - Voltage: ~5–7 V (loaded, lower than open-circuit)
   - Current: ~100–300 mA (depending on panel specs and sunlight)
   - Power: Calculated from V × I

**Troubleshooting - Zero or implausible readings:**
- **Zero voltage**: Check VCC connection to Pi 3.3 V (not 5 V). Verify INA219 VCC pin.
- **Zero current with panel illuminated**: Ensure the load (22 Ω resistor) is connected. An open-circuited panel produces no current.
- **Negative current**: This is normal if current direction reverses (e.g., panel voltage is insufficient to forward-bias the load, or if measuring battery charge). The INA219 supports bidirectional measurement.
- **Very high current**: Verify the shunt resistor value matches what the library expects (default 0.1 Ω).

### 4. Compare Readings Against a Multimeter

**Goal:** Validate INA219 accuracy against a reference multimeter.

**Steps:**
1. Set up the circuit with the test load.
2. Measure panel voltage with a multimeter directly at the panel terminals.
3. Compare to the INA219's `bus_voltage_v` reading.
4. Measure current with the multimeter in series (break the circuit and insert the meter).
5. Compare to the INA219's `current_mA` reading (convert mA to A if needed).
6. Calculate power manually (V × I) and compare to the INA219's `power_W` reading.

**Expected accuracy:**
- INA219 voltage accuracy: ±1–2 % (good for monitoring).
- INA219 current accuracy: ±1–3 % depending on gain and shunt resistor.
- Readings should be within ~10–20 % of multimeter values (environmental factors affect this).

**Troubleshooting - Large discrepancy:**
- Check multimeter connections and ranges.
- Verify the INA219's `SHUNT_OHMS` config matches the actual shunt resistor on the module.
- Ensure the INA219 gain is set appropriately (GAIN_1_4 for small currents, GAIN_1 for larger).
- Re-check the circuit wiring, especially the common-ground connection.

### 5. Test Under Different Lighting Conditions

**Goal:** Observe how readings vary with sunlight intensity.

**Steps:**
1. Take readings in full sunlight (panel directly facing the sun).
2. Take readings in partial shade (panel angled away from sun or partially covered).
3. Take readings indoors (panel under bright artificial light).
4. Record voltage, current, and power for each condition.

**Expected behavior:**
- Voltage: Relatively constant (panel characteristic), may drop slightly under load.
- Current: Proportional to sunlight intensity (more sun → more current).
- Power: Varies significantly with illumination.

**Note:** This prototype does not include active MPPT (maximum power point tracking). The fixed 22 Ω load means the panel operates at a specific voltage/current point determined by the panel's I-V curve and the load resistance.

### 6. Check Power and Energy Calculations Are Plausible

**Goal:** Verify that energy accumulation makes sense.

**Steps:**
1. Run the monitor for a known period (e.g., 10 minutes = 600 seconds).
2. Record the "Energy Today" value from the dashboard.
3. Calculate expected energy: If power is roughly constant at P watts, then
   Energy (Wh) = P × (600/3600) = P × 0.167.
4. Compare the displayed accumulated energy to the manual calculation.

**Example:** If average power is 0.5 W over 10 minutes:
Expected energy = 0.5 × 0.167 ≈ 0.083 Wh ≈ 83 mWh.

**Troubleshooting - Energy grows incorrectly:**
- If energy accumulates even when the panel is disconnected, check for sensor reads returning stale values.
- If energy jumps unexpectedly, check for large time gaps (dt) between samples (the energy tracker ignores gaps > MAX_GAP_SEC = 86400 s).
- If energy resets to zero after restart, verify the cumulative offset is stored in the database's `meta` table.

### 7. Confirm Database Logging and CSV Export

**Goal:** Ensure readings are stored and can be exported.

**Steps:**
1. Run the monitor for a few minutes.
2. Check the database file location (default: `~/solar_monitor/data/solar_readings.db` or `E:\GIT\workshop\solar_pi_project\data\solar.db`).
3. Query the database:

```bash
sqlite3 solar_readings.db "SELECT COUNT(*) FROM readings;"
```

4. Export to CSV:

```bash
python3 -c "
from src.database import Database
db = Database()
csv_text = db.export_csv()
with open('export.csv', 'w') as f:
    f.write(csv_text)
"
```

5. Open the CSV in a spreadsheet program and verify columns are correct.

**Troubleshooting - Database errors:**
- "database is locked": Ensure only one process writes to the database at a time. The project uses threading locks, but concurrent writes can still cause issues.
- "no such table": Run the app once to initialize the database (tables are created on first start).
- CSV export empty: Check that readings exist in the database. The first few samples may be stored before CSV export has data.

### 8. Verify Dashboard Updates and Historical Graphs

**Goal:** Ensure the web dashboard displays live data and historical graphs.

**Steps:**
1. Start the dashboard: `python src/app.py` or `./scripts/start.sh`.
2. Open a browser to `http://<PI_IP>:5000`.
3. Verify:
   - Live readings update (voltage, current, power).
   - Graphs show recent data points (voltage, current, power history).
   - "Energy Today" increases over time (when panel is producing power).
   - "Total Accumulated" also increases.
4. Select a different date in the history page (if applicable).
5. Use the CSV download link.

**Troubleshooting - Dashboard shows "---" or "Error":**
- Check the terminal running the Flask app for error messages.
- Verify the sensor is still connected and I²C communication is working.
- Refresh the browser page.
- If the dashboard was stopped and restarted, energy totals should continue from where they left off (restart-safe design).

### 9. Test Recovery After Sensor Disconnection/Application Restart

**Goal:** Ensure the system handles temporary disconnections gracefully.

**Steps:**
1. Start the monitoring system.
2. Observe normal operation for a few minutes.
3. Disconnect the INA219 (or unplug SDA/SCL).
4. Observe that the dashboard shows error status (not fabricated values).
5. Reconnect the INA219.
6. Observe recovery: the system should re-detect the sensor and resume normal readings.
7. Restart the Flask app (`Ctrl+C` then run again).
8. Verify energy totals continue from the last stored values (not reset to zero).

**Expected behavior:**
- During disconnection: dashboard shows error status, readings are "—" or "Error".
- After reconnection: normal readings resume; energy integration continues from the last valid cumulative value.
- After restart: the `cumulative_wh_offset` in the `meta` table ensures energy is not lost.

## Systematic Troubleshooting Guide

### Common Problems and Solutions

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| **INA219 not detected** (`i2cdetect` shows no address 0x40) | Wrong I²C address (A0/A1 connected differently) | Check A0/A1 pins; try connecting to 3.3 V or GND to set expected address. |
| | I²C not enabled on Pi | Run `raspi-config` → Interface Options → I²C → Yes, then reboot. |
| | Wrong wiring | Verify: VCC→pin1, GND→pin6, SDA→pin3, SCL→pin5. Use multimeter. |
| | Module defective | Try a different INA219 module. |
| **Zero voltage reading** | VCC not connected to 3.3 V (maybe connected to 5 V) | Move VCC wire to Pi physical pin 1 (3.3 V). |
| | Pi not powered | Ensure 5 V micro-USB power supply is connected. |
| | Multimeter measurement error | Double-check connections. |
| **Zero current with panel in sunlight** | No load connected | Connect the 22 Ω / 5 W test load across the panel. |
| | Panel open-circuit (no current flow possible) | Ensure panel has some illumination and load. |
| | Shunt resistor value mismatch | Verify the actual shunt resistor on the INA219 module (usually 0.1 Ω). |
| **Negative current reading** | Normal bidirectional measurement | This is expected; negative means current flows opposite to assumed direction. |
| | Battery charging (if battery added) | Not applicable until optional battery upgrade. |
| **Power reading much higher/lower than V × I** | Gain setting incorrect | Check `gain` configuration in the sensor code. GAIN_1_4 for ~500 mA max. |
| | ADC resolution affecting accuracy | Default 12-bit 128-sample is good for stationary monitoring. |
| **Energy accumulates even when panel disconnected** | Sensor returning last valid value | This is normal for the last-sampling design. The database stores ok=0 readings with NULL values. |
| | Cumulative offset not persisted | Ensure the app is started/stopped properly (offset is stored in `meta` table). |
| **Dashboard not accessible from another device** | Flask bound to 127.0.0.1 (localhost only) | The app uses `host="0.0.0.0"` to listen on all interfaces. |
| | Network firewall blocking port 5000 | Ensure port 5000 is open on the local network. |
| | Pi IP address changed | Run `hostname -I` again to get the current IP. |
| **Dashboard shows stale/old values** | Browser caching | Refresh the page (Ctrl+F5). |
| | Sensor sampling interval too slow | 1-second sampling is deliberate; faster sampling offers diminishing returns. |
| **CSV export empty or malformed** | No readings in database yet | Run the monitor for at least 30 seconds before exporting. |
| | Date filter too restrictive | Try exporting without date filter first. |
| **Large discrepancy vs. multimeter** | Incorrect shunt resistor value | Measure the actual shunt on the INA219 module and update `SHUNT_OHMS` in `src/config.py`. |
| | Gain too low/high for the current range | Adjust `MAX_AMPS` in `src/config.py` to match expected panel current. |
| | Multimeter in wrong range | Ensure multimeter ranges are appropriate (e.g., 20 V range for voltage, 200 mA for current). |

### Escalation Steps

If none of the above resolves the issue:

1. **Verify basic I²C communication**: Run `i2cdetect -y 1` and note all addresses. Compare against the INA219 datasheet address.
2. **Test with CircuitPython or Arduino**: If available, load a simple INA219 sketch to confirm the module works independent of the Raspberry Pi Python environment.
3. **Check for electromagnetic interference (EMI)**: The I²C bus can be sensitive to noise. Keep wires short, away from power cables, and use the breadboard's power rails carefully.
4. **Review system logs**: `dmesg | grep i2c` may show I²C bus errors.
5. **Contact project mentor**: If the issue persists after all troubleshooting steps, consult your instructor or project mentor.

### Verification Checklist

Before considering the hardware "tested and working," confirm:

- [ ] `i2cdetect -y 1` shows address 0x40 (or your expected address)
- [ ] Sensor readings are reasonable (voltage within panel's range, current within expected limits)
- [ ] Multimeter comparison shows within ~20% agreement (environment-dependent)
- [ ] Dashboard is accessible from another device on the same network
- [ ] Energy totals increase when the panel is in sunlight with the load connected
- [ ] Restarting the app preserves cumulative energy (check the database `meta` table)
- [ ] CSV export produces a file with correct column headers and data
- [ ] No smoke, overheating, or unusual smells from any components