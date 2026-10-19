# Troubleshooting

## Dashboard will not load / "Unable to reach the monitor API"

- Confirm the app is running: `./scripts/stop.sh && ./scripts/start.sh`
- Confirm the port: default 5000, check `PORT` in `.env`/`config.json`
- Confirm the bind address: `HOST=0.0.0.0` allows LAN access; `127.0.0.1` is local only
- From another device, use `http://<PI-IP>:5000/`, not `localhost`

## Sensor shows "disconnected" (hardware mode)

- Run `sudo i2cdetect -y 1` — the INA219 must appear. If not:
  - Re-check wiring per `docs/HARDWARE_WIRING.md` (POWER OFF first)
  - Confirm I²C is enabled and the Pi has rebooted
  - Confirm `INA219_I2C_ADDRESS` matches the detected address
- Confirm `SENSOR_MODE=hardware` in `.env`
- The app never substitutes simulated data for a failed physical reading, so a
  genuine disconnection shows as disconnected until the sensor recovers.

## Readings are all zero / night-time

- The simulated sensor produces a day/night curve; power is near zero at night.
- In hardware mode, cover/uncover the panel to confirm current changes.

## "Address already in use" (port 5000)

- Another instance is running: `./scripts/stop.sh`, or kill the process on port 5000.
- Or change `PORT` in `.env`/`config.json`.

## Database is locked / errors inserting

- Only one instance should write to `solar_monitor.db` at a time. Stop other
  instances before starting a new one.

## No readings after restart

- Readings persist in `solar_monitor.db`. Accumulated energy is recomputed from
  persisted measurements, so history survives restarts.
- Energy generated while the app was stopped is not recorded (no samples were
  taken); it is treated as unknown, not zero.

## CSV/JSON export empty (404)

- No measurements fall within the requested date range. Broaden the range or
  clear the filters.

## INA219 library missing on the Pi

- Install: `pip install ina219` inside the virtual environment, then re-run
  `scripts/check_hardware.py`.

## Logs

- App log: `logs/solar_monitor.log` (when started with `scripts/start.sh`)
- systemd: `journalctl -u solar-monitor.service -f`
