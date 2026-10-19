# Example dashboard layout

## Dashboard page (`/`)

Top bar: page title + status chip (green `● sensor OK` or red `● sensor error`).

Six stat cards (responsive grid, single column on phones):
1. Panel voltage — value in V
2. Current (load) — value in mA
3. Instant power — value in W
4. Energy today — value in Wh (resets at local midnight)
5. Total energy — value in Wh (cumulative, survives restart)
6. Status — "Sensor connected" or error text + timestamp

Two Chart.js line cards below:
- Voltage & Current (last hour) — dual axis (V left, mA right)
- Power & Energy (last hour) — dual axis (W left, Wh right)

Data polls `/api/current` and `/api/history` every 2 seconds.

## History & CSV page (`/history`)
- From/To `datetime-local` filters
- Load button to fetch filtered readings via `/api/history`
- Read-only table: timestamp, voltage (V), current (mA), power (W), energy (Wh), status, error
- Download CSV button → `/export.csv?start=&end=`

## Mobile behavior
- Single-column stat cards stack on narrow screens.
- Charts shrink to fit (`responsive: true`).
- `datetime-local` inputs use the phone's native date/time picker.
- Fonts and tap targets sized for touch.

## Error states
- During a sensor disconnection, stat cards show `—`, the status chip turns red,
  and the error message is shown. Failed samples are still logged (ok=0) so
  gaps are visible in history rather than replaced by fabricated zeros.
