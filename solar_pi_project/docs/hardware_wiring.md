# Solar Panel Performance Monitor - Hardware Wiring

## INA219 Pin Identification

Before wiring, verify the actual pin labels on your INA219 board. Not all 8-pin
breakout boards have the same layout. The most common pinout (as used in this project) is:

| Pin Number | Signal      | Description                              |
|------------|-------------|------------------------------------------|
| 1          | SDA         | I²C Data line (connect to Pi GPIO 2)     |
| 2          | VCC         | Power supply (3.3 V from Pi)             |
| 3          | GND         | Ground (connect to Pi GND)               |
| 4          | A0 / ADDR   | I²C address selector (pull high or low)  |
| 5          | A1 / ADDR   | I²C address selector (pull high or low)  |
| 6          | SCL         | I²C Clock line (connect to Pi GPIO 3)    |
| 7          | V- / SHUNT- | Negative terminal of the current shunt   |
| 8          | V+ / SHUNT+ | Positive terminal of the current shunt   |

> **Important:** Some INA219 modules swap the positions of the SHUNT pins or label
> them differently (e.g., VIN+, VIN-). Always use a multimeter to verify continuity
> before connecting to the Raspberry Pi. Do not assume pin numbers based on generic
> diagrams.

## INA219 to Raspberry Pi 3 A+ Connections

The following table uses **physical pin numbers** (as numbered on the Pi header),
not GPIO numbering.

| INA219 Pin | Raspberry Pi Physical Pin | Function               |
|------------|---------------------------|------------------------|
| VCC        | 1 (3.3 V)                 | Power supply           |
| GND        | 6 (GND)                   | Ground common          |
| SDA        | 3 (GPIO 2 / SDA)          | I²C Data               |
| SCL        | 5 (GPIO 3 / SCL)          | I²C Clock              |
| A0         | —                         | Can be left floating or pulled to 3.3 V |
| A1         | —                         | Can be left floating or pulled to 3.3 V |
| V- / SHUNT-| Connected to load side    | Shunt negative terminal|
| V+ / SHUNT+| Connected to panel side   | Shunt positive terminal|

### Handling A0 and A1

- A0 and A1 are I²C address selectors. By default, they can be floated (not connected).
- If you need to change the I²C address, connect A0/A1 to 3.3 V (1) or GND (0).
- The default address for the common INA219 module is **0x40** (A0=0, A1=0).
- Leaving A0 and A1 unconnected is fine for a single-sensor setup.

## Solar Panel Measurement Circuit

### Polarity and Connections

The INA219 measures current flowing through its internal shunt resistor, which is
connected between the V+ and V- pins. The module is designed for **bidirectional**
current monitoring.

| INA219 Terminal | Connection                              | Polarity Note                     |
|-----------------|-----------------------------------------|-----------------------------------|
| VIN+ (or V+)    | Connect to solar panel positive terminal| Panel positive -> INA219 VIN+     |
| VIN- (or V-)    | Connect to test load/solar panel negative| Common ground with Pi             |

> **Important:** The solar panel's negative terminal (or common return) must be
> connected to the Raspberry Pi's GND pin. This establishes the **common-ground**
> requirement essential for the INA219 to measure voltage and current correctly.

### Complete Wiring Diagram

```
            +----------------------+
            |  Solar Panel (~6V)   |
            +----------+-----------+
                       |
                       | VIN+ (Panel Positive)
                       |
                +-----+-----+
                |  INA219   |
                |  VIN+      |
                +-----+-----+
                       |
                       | Shunt resistor (internal)
                       |
                +-----+-----+
                |  INA219   |
                |  VIN-      |
                +-----+-----+
                       |
                       | VIN- / Load -> 22 Ω / 5 W resistor -> Common return
                       |
                       +----------------------+
                                              |
                                              | GND (common)
                                              |
                                       +-----+-----+
                                       | Raspberry Pi|
                                       |  Physical 6   |
                                       |  (GND)       |
                                       +-----+-----+
                                              |
                +----------------------+------------+ |
                |  INA219              Pi         | |
                |  VCC          <---|  Physical 1 | |
                |  (3.3 V)               (3.3 V)  | |
                |  GND          <---|  Physical 6   | |
                |  (GND)               (GND)   | |
                |  SDA        <---|  Physical 3   | |
                |  (GPIO 2 / SDA)      (GPIO 2) | |
                |  SCL        <---|  Physical 5   | |
                |  (GPIO 3 / SCL)      (GPIO 3) | |
                +----------------------+-----------+

```

> **Key Points:**
> - The INA219's internal shunt resistor measures the current flowing from VIN+ to VIN-.
> - If current flows into the panel (e.g., battery charging), the reading will be negative
>   (supported by the INA219 library).
> - The load (22 Ω / 5 W resistor) is connected across the panel, drawing current through
>   the INA219's shunt.
> - **Never** connect solar-panel voltage directly to Raspberry Pi GPIO pins — the Pi's
>   GPIO pins are not rated for 5–10 V and will be damaged.

## Common-Ground Requirements

- The INA219, Raspberry Pi, and solar panel/share load must share a **common ground**.
- Connect the Pi's GND (physical pin 6) to the INA219 GND and to the solar panel's
  negative terminal.
- This ensures the INA219's voltage measurement (VBus) and current measurement (shunt)
>  refer to the same reference point as the Pi's logic.

## Voltage and Current Checks Before Applying Power

Before connecting the circuit to the Raspberry Pi, verify these conditions:

1. **Solar panel open-circuit voltage** should be within the INA219's operating range
   (typically 0–32 V, but verify your specific module). For a "~6 V, 3 W" panel, expect
   an open-circuit voltage of about 7–9 V under standard conditions.

2. **Maximum expected current**: A 3 W / 6 V panel has a short-circuit current of roughly
   3 W / 6 V = 0.5 A (500 mA), well within the INA219's ±3.2 A default range.

3. **Load resistor power dissipation**: The 22 Ω / 5 W resistor, when connected to a
   6 V panel, will dissipate P = V²/R = 36/22 ≈ 1.64 W, safely within the 5 W rating.

4. **No direct connection** of panel voltage to Pi GPIO pins at any point.

5. **Shunt voltage** is typically very small (millivolts). The INA219 amplifies this
   and provides the bus voltage and current values via I²C.

If the 22 Ω / 5 W resistor is deemed unsuitable for your specific panel, a safer
alternative is a **10 Ω / 5 W resistor**, which would dissipate ~3.6 W at 6 V — still
within rating but limiting current to ~0.6 A. Alternatively, use a **power resistor
bank** with appropriate ratings, or reduce the resistance only after calculating the
expected power dissipation.

> **Never** select a resistor based on resistance alone — always verify its power
> rating exceeds the expected dissipation by a safe margin (2× or more is recommended).