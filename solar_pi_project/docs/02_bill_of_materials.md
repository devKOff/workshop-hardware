# Bill of materials (BOM)

| # | Item | Qty | Purpose | Notes / what to verify |
|---|------|-----|---------|------------------------|
| 1 | Raspberry Pi 3 Model A+ | 1 | Main controller; runs Flask + logger | microSD with Raspberry Pi OS; 5 V micro-USB supply |
| 2 | microSD card (8 GB+) | 1 | OS + application + database | Use official Raspberry Pi Imager to flash |
| 3 | 5 V micro-USB power supply | 1 | Powers the Pi separately | Do not power Pi from the solar panel |
| 4 | INA219 current/power monitoring breakout | 1 | Measures bus voltage, shunt voltage, current, power | **Verify pin labels, shunt value (typically 0.1 Ω), I²C address** |
| 5 | Solar panel ~6 V, 3 W | 1 | Source under test | **Measure actual Voc and Isc in sunlight before connecting** |
| 6 | Resistor 22 Ω, 5 W wirewound | 1 | Test load | Gets warm; keep away from flammables. Alternatives: 47 Ω or 100 Ω |
| 7 | Breadboard | 1 | Prototyping connections | |
| 8 | Male-to-male jumper wires | ~6 | Pi ↔ INA219 (VCC, GND, SDA, SCL) | |
| 9 | Insulated connecting wires | several | Panel ↔ INA219 ↔ load | Rated for at least the panel voltage/current |
| 10 | Multimeter | 1 | Verify Voc, Isc, continuity, compare readings | Essential for validation |

## Optional future upgrades (not required for base build)

| Item | Purpose |
|------|---------|
| BH1750 light-intensity sensor | Sunlight / illuminance (lux) — note: lux ≠ solar irradiance W/m² |
| DS18B20 temperature sensor | Panel or ambient temperature |
| Additional load resistors (47 Ω, 100 Ω) | Cooler / lower-current load options |
| Enclosure + mounting hardware | Physical protection and outdoor/sun mounting |
| Charge controller | **Required only if you later connect a battery** |

## Hardware assumptions to document in your report

- INA219 shunt resistor = 0.1 Ω (verify on actual board; not universal).
- INA219 I²C address = 0x40 with A0=A1=GND (verify with `i2cdetect`).
- INA219 bus-voltage tolerance = 0–26 V typical (verify your variant's absolute max).
- Panel Voc and Isc = measured values (not guesses; "6 V, 3 W" is nominal only).

If a specification is missing from a component you purchased, measure it with a
multimeter or obtain the datasheet before wiring. Do not proceed on assumptions.
