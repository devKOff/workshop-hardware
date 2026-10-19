# Calculations and validation

All formulas below use SI units. Example numbers are **illustrative only** —
they are not actual sensor readings.

## 1. Power from voltage and current

Instantaneous electrical power:

```
P (W) = V (V) × I (A)
```

The INA219 reports bus voltage `V` (V) and current `I` (mA). Convert mA → A:

```
I (A) = current_mA / 1000
P (W) = bus_voltage_v × (current_ma / 1000)
```

The library also returns `power_mw` directly, so:

```
P (W) = power_mw / 1000
```

### Example (illustrative)
- Measured: V = 5.50 V, I = 250 mA = 0.250 A
- P = 5.50 × 0.250 = **1.375 W**

## 2. Energy from power integrated over time

Energy is the time integral of power. With discrete samples every Δt seconds:

```
ΔE (Wh) = P (W) × Δt (s) / 3600
E_cumulative (Wh) = Σ ΔE over all samples
```

At a 1-second sample interval:
- If P = 1.375 W constantly for 1 hour: E = 1.375 × 1 = **1.375 Wh**.
- If P = 1.375 W for just one 1-second sample: ΔE = 1.375 / 3600 ≈ **0.00038 Wh**.

The code (`src/energy_tracker.py`) integrates this way and stores cumulative Wh
in SQLite so it survives restarts.

## 3. Daily energy totals

Each day's energy is summed from midnight to midnight:

```
E_day (Wh) = Σ P_k × Δt_k / 3600   for all samples k on that local date
```

The tracker resets the daily accumulator when the local date changes (see
`src/energy_tracker.py`). The previous day's total is preserved in the
`daily_totals` table, so history is never lost.

### Example (illustrative)
- Morning: 0.2 Wh
- Midday peak: 1.1 Wh
- Afternoon cloud: 0.4 Wh
- Daily total ≈ **1.7 Wh/day**

## 4. Average power over a selected interval

```
P_avg (W) = E_interval (Wh) / t_interval (h)
```

### Example (illustrative)
- Over 2 hours the panel generated 2.4 Wh.
- P_avg = 2.4 Wh / 2 h = **1.2 W**

## 5. Why measured output varies

| Factor | Effect |
|--------|--------|
| Sunlight (irradiance) | More irradiance → higher current (roughly linear) |
| Panel temperature | Higher temperature → slightly lower voltage and efficiency |
| Panel orientation/tilt | Direct perpendicular sunlight maximizes output |
| Load resistance | Determines operating point on the panel's I–V curve; a fixed resistor is **not** at the maximum-power point |

## 6. Fixed resistor ≠ MPPT

A solar panel's maximum power point changes with sunlight and temperature. A
fixed 22 Ω resistor simply sets one operating point; the panel will rarely be
at its true maximum power. This project measures performance **at that fixed
load**, it does not perform maximum-power-point tracking (MPPT). An MPPT
experiment is listed under future improvements (docs/08).

## 7. Lux is not solar irradiance

If you later add a BH1750 light sensor, it reports **illuminance in lux**.
Lux measures perceived visible brightness to the human eye, weighted by the
eye's sensitivity curve. Solar irradiance (W/m²) measures total electromagnetic
power across the spectrum. The two are related but **not interchangeable**;
converting lux → W/m² requires knowing the light source's spectrum. For
sunlight a rough rule of thumb is ~0.0079 W/m² per lux, but it varies. Treat
lux as a relative "is it sunny?" indicator, not an irradiance measurement.

## Validation approach (student project)

1. Measure panel voltage with a multimeter; compare to the dashboard voltage
   (should agree within a few %).
2. Measure current with the multimeter in series; compare to dashboard current.
3. Check P = V × I with your multimeter numbers; compare to dashboard power.
4. Leave the system running for an hour under steady light; verify
   energy ≈ power × time (within integration error).
