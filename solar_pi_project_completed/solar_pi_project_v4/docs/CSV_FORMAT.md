# CSV Format

Columns (fixed order):
`timestamp, voltage_v, current_ma, current_a, power_w, energy_wh_increment,
 daily_energy_wh, total_energy_wh, session_id, sensor_mode, sensor_status`

- UTF-8 with BOM (`utf-8-sig`).
- ISO 8601 timestamps with timezone.
- Real stored rows only.
- Written to a temp file then atomically renamed.