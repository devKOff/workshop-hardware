# Test Plan — Solar Panel Performance Monitor

## Automated tests (run on Windows laptop, no hardware required)

| File | What it covers |
|------|----------------|
| `tests/test_config.py` | Config loading, .env / config.json / env var precedence, type coercion (hex I²C address), validation rules |
| `tests/test_sensor_service.py` | Simulated sensor readings, unit conversions (V/mA/A/W), day/night curve, determinism with seed, INA219 driver guarded import, sensor service start/stop, duplicate-start prevention, persistence, shutdown |
| `tests/test_energy_service.py` | Wh integration (trapezoidal), regular and irregular intervals, duplicate/zero-duration intervals, daily energy rollover at local midnight, empty input |
| `tests/test_database.py` | SQLite insert/retrieve, time-range and limit queries, restart persistence (same file, new connection), failed-measurement recording, daily summaries, error on bad path |
| `tests/test_api.py` | All JSON API endpoints, status codes, invalid input handling (400), empty-state (404), sampling start/stop, HTML pages |
| `tests/test_exports.py` | CSV and JSON export structure, columns, range filtering, empty range (404) |
| `tests/test_integration.py` | Full sample → persist → API roundtrip, duplicate sampler prevention, graceful shutdown, DB error surfacing, sensor failure propagation (no simulated fallback), restart persistence, endpoint schema |

### Run the suite

```powershell
python -m pytest
```

With coverage:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

## Skipped tests

The INA219 hardware driver tests (`test_ina219_*`) are skipped on Windows because
the `ina219` library requires Linux `/dev/i2c` and is not installable there.
They execute on the Raspberry Pi during hardware validation.

## Physical hardware tests (Raspberry Pi only — pending until hardware available)

These cannot be automated on the laptop and require the actual Pi + INA219 +
solar panel + 33 Ω resistor.

| # | Test | Pass criterion |
|---|------|----------------|
| H1 | I²C detection | `sudo i2cdetect -y 1` shows the INA219 address |
| H2 | Hardware read | `python scripts/check_hardware.py` returns voltage/current/power |
| H3 | Multimeter comparison | Pi current/power within ~10% of a multimeter in series |
| H4 | Energy over time | Accumulated Wh increases monotonically while illuminated |
| H5 | Night rollover | Daily energy resets at local midnight |
| H6 | LAN access | Dashboard reachable from a phone/laptop at http://<pi-ip>:5000/ |
| H7 | Disconnection/recovery | Dashboard shows "disconnected" when sensor unplugged, recovers when reconnected |

Record results in `docs/TEST_RESULTS.md` when hardware testing is performed.

## Test honesty

- No test fabricates hardware readings.
- Simulated sensor is used for all laptop tests.
- Physical testing is marked **pending** until the Pi and INA219 are available.
