# Circuit schematic (text) and safety checks

## Text schematic

```
                 +---------------------------------------+
                 |  Solar panel (~6 V nominal, 3 W)      |
                 |                                       |
              +--|---+                          +---|--+
              |  (+) |                          |  (−) |
              +--|---+                          +---|--+
                 |                                   |
          panel  |                                   |  load
          +      |          INA219 breakout          |  22 Ω, 5 W
          wire   +------- VIN+          VIN− --------+----/\/\/----+
                   |  shunt (0.1 Ω typical, on board)        |
                   |                                         |
              [GND]-------------------------------------------+---- common ground
                   |                                          |
          Pi pin 1 3.3 V ─────────────────────────── VCC     |
          Pi pin 6 GND  ─────────────────────────── GND ----+
          Pi pin 3 GPIO2/SDA ────────────────────── SDA
          Pi pin 5 GPIO3/SCL ────────────────────── SCL
                   |
          [Raspberry Pi 3 A+]  ← powered by separate 5 V micro-USB
```

## How the INA219 measures

| Quantity | Where it is measured | Meaning |
|----------|---------------------|---------|
| Bus voltage (V) | Between VIN+ and GND | Solar panel terminal voltage at the high side |
| Shunt voltage (V) | Between VIN+ and VIN− | Voltage dropped across the internal 0.1 Ω (typical) shunt |
| Current (A) | shunt_voltage / shunt_ohms | Current flowing panel → load through the shunt |
| Power (W) | bus_voltage × current | Instantaneous electrical power delivered to the load |

Because the shunt is on the **high side** (between panel + and the load), the
load's other terminal connects to panel − / common GND, and the Raspberry Pi's
GND is tied to that same point. No high voltage from the panel ever reaches the
Pi.

## Pre-connection safety checks (do all of these)

### 1. Panel open-circuit voltage (Voc)
Measure the panel's Voc with a multimeter in bright sunlight (panel
disconnected from everything). A "6 V" panel often measures 7–9 V open circuit.

- **Requirement:** Voc must be below the INA219 breakout's rated bus-voltage
  input. Common breakouts tolerate 0–26 V on the ADC inputs (absolute maximum
  depends on variant, often ~30–40 V). Confirm your board's rating.
- If Voc is above the breakout's limit, do NOT connect it. Use a smaller panel
  or add a voltage divider (which reduces accuracy) — or choose a panel whose
  Voc is safely within range.

### 2. Maximum expected current vs shunt rating
- Estimate short-circuit current: Isc ≈ panel_rating_W / panel_rating_V
  (e.g., 3 W / 6 V ≈ 0.5 A). Real Isc may be higher; measure it if possible.
- With the 22 Ω load at ~6 V: I ≈ 6 / 22 ≈ 0.27 A.
- Shunt drop at 0.27 A with 0.1 Ω shunt: 0.27 × 0.1 = 27 mV.
- Common 0.1 Ω shunt breakouts are rated for ±320 mV full scale (≈ ±3.2 A) or
  ±40 mV (≈ ±0.4 A) depending on gain setting. 27 mV fits either, but leave
  headroom: if full sun pushes current higher, use the ±320 mV range
  (configure via `MAX_AMPS` in `src/config.py`, e.g. 2.0 A).
- **Requirement:** expected max current ≪ shunt/breakout rating. If your panel
  can exceed ~2 A, choose a larger shunt-friendly load resistance or a lower
  MAX_AMPS calibration, and re-check.

### 3. Load resistor suitability
- At 6 V across 22 Ω: P = V² / R = 36 / 22 ≈ 1.64 W.
- Resistor rating: 5 W. 1.64 W < 5 W → within rating, but the resistor will get
  warm to hot in continuous sun.
- **Requirement:** resistor power dissipation must stay below its rating with
  margin, and it must be mounted away from plastic/flammable material.

### 4. Resistor power & temperature safety
- A 5 W wirewound resistor dissipating 1.6 W can reach elevated temperatures.
- Mount it so it cannot touch the breadboard, plastic enclosure, wires, or
  anything flammable. Consider a higher-resistance load (e.g., 47 Ω or 100 Ω)
  if you want cooler operation; trade-off is lower current/power readings.

### 5. No panel voltage to Pi GPIO
- Verified by construction: only 3.3 V, GND, SDA, SCL connect Pi ↔ INA219.
- Double-check with a multimeter before powering the Pi: measure resistance
  from each INA219 logic pin (VCC, SDA, SCL) to panel + — it should be open /
  high, not a short to panel voltage.

## If the specified resistor is unsuitable

The 22 Ω, 5 W resistor is generally acceptable for a ~6 V, 3 W panel, but it
runs warm. Safer/cooler alternatives:

| Load resistor | Approx current @ 6 V | Approx power in resistor | Comment |
|---------------|---------------------|--------------------------|---------|
| 22 Ω, 5 W | ~0.27 A | ~1.6 W | Original spec; warm but OK |
| 47 Ω, 5 W | ~0.13 A | ~0.77 W | Cooler; safer for demos |
| 100 Ω, 2 W | ~0.06 A | ~0.36 W | Very cool; small readings |

**Recommendation:** Start with the 22 Ω resistor if you want readings near the
panel's rated output, but mount it carefully and expect heat. For a classroom
demo where students touch the board, use 47 Ω or 100 Ω to keep the resistor
cool, understanding that measured power will be lower (that is expected — a
fixed resistor is not MPPT; see docs/06_calculations.md).

## Hardware assumptions to state in your report

- INA219 shunt = 0.1 Ω (verify; some boards differ).
- INA219 max bus voltage = 26 V typical (verify your variant).
- Panel Voc and Isc must be measured with a multimeter before first connection.
- Pi is powered separately; no panel voltage on GPIO.

If any specification is missing from your components, measure it or obtain the
datasheet before proceeding — do not guess.
