# Solar Panel Performance Monitor - Circuit Schematic

## Text-Based Circuit Diagram

The following schematic shows the complete wiring connection between the solar panel,
INA219 sensor, and Raspberry Pi 3 Model A+.

```
                           +---------------------+
                           |   Solar Panel (~6V) |
                           |  Open-circuit: ~7-9V|
                           +---------+-----------+
                                   |
                                   | Positive (+)
                                   v
                                +-----+
                                | VIN+|  INA219 Current Shunt
                                |     |  (internal ~0.1 Ω)
                                +-----+
                                   |
                                   | Current flows when panel
                                   | supplies power to load
                                   v
                                +-----+
                                | VIN-|  INA219 Current Shunt
                                |     |  (returns to panel negative)
                                +-----+
                                   |
                                   +----------------------+
                                   |                      |
                                   |   Load (22 Ω / 5W)   |
                                   |   Test load resistor |
                                   |                      |
                                   +----------+-----------+
                                              |
                                              | Negative/Return (GND)
                                              |
                                +---------+-----------+
                                |   Raspberry Pi 3 A+ |
                                |   Physical Pin 6    |  (GND)
                                +---------+-----------+
                                          |
                                          | GND common
                                          |
                      +-----------------+-----------------+
                      |                                     |
              Physical Pin 1 (3.3 V)           Physical Pin 3 (GPIO 2 / SDA)
                      |                                     |
                      |                                     | INA219 VCC
              Physical Pin 5 (GPIO 3 / SCL)---|---------|
                      |                                     | INA219 SCL
                      |                                     |
              Physical Pin 6 (GND) -----------|---------|
                                                    | INA219 GND
                                                    |
                           +-----+--------+--------+-----+
                           |   A0  |   A1   |           |   (I²C address
                           |       |          |           |   address selectors)
                           +-----+--------+--------+-----+
                                                                   
                           (Leave A0 and A1 floating for default address 0x40)
```

## Key Connections Detail

### INA219 to Raspberry Pi 3 A+ (4 wires)

| Pi Physical Pin | Signal | INA219 Pin | Function |
|-----------------|--------|------------|----------|
| 1 (3.3 V) | VCC | 2 | Power supply (3.3 V) |
| 6 (GND) | GND | 3 | Ground common |
| 3 (GPIO 2) | SDA | 1 | I²C Data line |
| 5 (GPIO 3) | SCL | 6 | I²C Clock line |

> **Note:** Pins A0 and A1 (pins 4 and 7 on some module layouts) are I²C address selectors.
> For the default module address 0x40, leave A0 and A1 unconnected (floating).

### Solar Panel + Load Circuit

```
                   +------------------+        +------------------+
                   |                  |        |                  |
                   |   Solar Panel   |        |   22 Ω / 5 W     |
                   |   (~6V, 3W)     |        |   Power Resistor   |
                   |   Positive      |        |                  |
                   +--------+--------+        +--------+---------+
                          |                      |
                          |                      |
                          v                      v
               +---------+-----------+  +----------+----------+
               |         INA219    |  |        Load         |
               |   VIN+ ---+--------+  |  +--------+          |
               |             |          |  |  22 Ω    |          |
               |   VIN- ---+--------+  |  +--------+          |
               |         |            |  |          |          |
               +---------+------------+  +----------+          |
                                   |                   |
                                   |                   |
                              Panel Negative    Resistor Other Lead
                                   |                   |
                                   +---------+---------+
                                               |
                                               | GND Common
                                               |
                                      +----v----+
                                      | Raspberry|
                                      |  Physical|
                                      |   Pin 6 GND|
                                      +----------+

```

> **Current measurement principle:** The INA219 has an internal shunt resistor (typically
> 0.1 Ω). Current flowing from VIN+ to VIN- develops a small voltage across the shunt
> (V = I × R). The INA219 amplifies this and reports:
> - Bus voltage (VIN+ relative to VIN- common)
> - Shunt voltage (voltage across the resistor)
> - Current (calculated from shunt voltage / shunt resistance)
> - Power (bus voltage × current)

### Common-Ground Requirement

- The solar panel's negative terminal (or common return) MUST be connected to the
  Raspberry Pi's GND (physical pin 6).
- This establishes the **common-ground** essential for the INA219 to measure both
  bus voltage and current correctly.
- Without common ground, the INA219 readings will be incorrect or erratic.

### Polarity Notes

| Connection | Polarity | Description |
|------------|----------|-------------|
| Solar Panel + | Positive | Panel's positive terminal connects to INA219 VIN+ |
| Solar Panel - | Negative/Return | Panel's negative/ground connects to Pi GND AND INA219 VIN- |
| Load resistor | Either | The 22 Ω / 5 W resistor can be connected either way (it's non-polar) |
| INA219 VCC | 3.3 V | Connect to Pi 3.3 V (physical pin 1), NOT 5 V |

### Pre-Connection Safety Checks

Before applying power, verify:

1. **Solar panel open-circuit voltage**: Should be within INA219's operating range.
   - For a "~6 V, 3 W" panel, expect 7–9 V under open-circuit conditions.
   - INA219 typical VBus range: 0–32 V (verify your specific module).

2. **Maximum expected current**: A 3 W / 6 V panel has a short-circuit current of
   roughly 3 W / 6 V = 0.5 A (500 mA), well within the INA219's ±3.2 A default
   range (with 0.1 Ω shunt resistor).

3. **Load resistor power dissipation**: At 6 V, the 22 Ω / 5 W resistor dissipates:
   P = V²/R = 36/22 ≈ 1.64 W, safely within the 5 W rating.

4. **No direct connections**: Panel voltage must never go directly to Pi GPIO pins.

5. **Shunt resistor verification**: Measure the actual shunt resistor on your INA219
   module (typically 0.1 Ω). This determines the current measurement range.

If the 22 Ω / 5 W resistor is unsuitable for your panel:
- A **10 Ω / 5 W** resistor would dissipate ~3.6 W at 6 V, limiting current to ~0.6 A.
- A **power resistor bank** with appropriate ratings.
- Always verify the resistor's power rating exceeds the expected dissipation by
  at least 2× for safe operation.

### INA219 Module Pin Variants

> **Important:** Not all INA219 breakout boards have the same pinout. The diagram
> above shows the most common layout. Before wiring:
> 1. **Identify the VCC and GND pins** using a multimeter (verify continuity to 3.3 V
>    and GND respectively).
> 2. **Identify SDA and SCL pins** (these are usually the two I²C data/clock pins).
> 3. **Identify the SHUNT/VIN pins** - these are the current-sensing terminals.
> 4. **Check A0/A1 address pins** - these may be on different pins than shown here.

> Use the multimeter's continuity/diode mode to trace each pin to its function if
> the silkscreen labels are unclear or faded.