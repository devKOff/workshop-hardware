# Wiring table — INA219 to Raspberry Pi 3 Model A+

**Read this entire section before connecting anything.**

## ⚠️ Verify your exact board first (mandatory)

Eight-pin INA219 breakout boards are NOT all laid out the same way. Some label the
current-sensing terminals as `VIN+` / `VIN−`, others as `+` / `−` or `VS+` / `VS−`.
Some boards bring out A0/A1; some do not.

Before wiring, identify every pin on YOUR board by reading the silkscreen and, if
in doubt, by checking continuity with a multimeter:

| Function | What it is | Typical label you might see |
|----------|-----------|-----------------------------|
| VCC | Logic power (3.3 V from Pi) | VCC, 3V3, VDD |
| GND | Logic / sensor ground | GND, – |
| SDA | I²C data | SDA, DATA |
| SCL | I²C clock | SCL, CLK |
| VIN+ | High side of shunt — connects to panel + | VIN+, +, VS+, IN+ |
| VIN− | Low side of shunt — connects to load | VIN−, −, VS−, IN− |
| A0 | I²C address bit 0 (if present) | A0, AD0 |
| A1 | I²C address bit 1 (if present) | A1, AD1 |

**Logic pins (VCC, GND, SDA, SCL) go to the Raspberry Pi. Current-sensing
terminals (VIN+, VIN−) go ONLY to the solar panel / load circuit — never to a
Pi GPIO pin.**

## INA219 → Raspberry Pi pin table (common arrangement)

| INA219 pin | Wire to Pi physical pin | Pi function | Purpose |
|------------|------------------------|-------------|---------|
| VCC | pin 1 | 3.3 V | Powers the INA219 logic |
| GND | pin 6 | GND | Common ground (Pi + sensor + panel negative return) |
| SDA | pin 3 | GPIO 2 / SDA | I²C data |
| SCL | pin 5 | GPIO 3 / SCL | I²C clock |

Raspberry Pi 3 A+ 40-pin header (relevant pins):

```
Pin 1  3.3 V      ← INA219 VCC
Pin 3  GPIO2 SDA  ← INA219 SDA
Pin 5  GPIO3 SCL  ← INA219 SCL
Pin 6  GND        ← INA219 GND
```

Pi 3 A+ has fewer pins than the B models, but pins 1, 3, 5, 6 exist and work
the same way. Any other GND pin (9, 14, 20, 25, 30, 34, 39) may also be used
for the common-ground connection.

## Handling A0 and A1 (address selection)

If your module exposes A0 and A1, they set the I²C address:

| A1 | A0 | I²C address |
|----|----|-------------|
| GND | GND | 0x40 (default) |
| GND | VCC | 0x41 |
| VCC | GND | 0x42 |
| VCC | VCC | 0x43 |

(Additional addresses 0x44–0x47 exist on some variants via other pin strapping;
check your breakout's datasheet.)

**Recommended for this project:** tie A0 and A1 to GND (or leave them unconnected
if the board has internal pull-downs) so the address is **0x40**, then confirm with
`sudo i2cdetect -y 1`. Update `INA219_ADDRESS` in `src/config.py` if your board
responds at a different address.

Do NOT leave A0/A1 floating if the board has no pull resistors — a floating
address pin can produce an unstable or wrong I²C address.

## Solar panel measurement circuit (current-sensing path)

The INA219 is a **high-side** monitor: its shunt resistor sits between VIN+ and
VIN−, and current flows from the panel into VIN+, through the shunt, out of
VIN−, and into the load.

| Point | Connects to |
|-------|-------------|
| Solar panel **+** | INA219 **VIN+** |
| INA219 **VIN−** | One end of the **22 Ω, 5 W load resistor** |
| Other end of load resistor | Solar panel **−** (negative terminal) |
| Solar panel **−** | INA219 **GND** and Pi **GND** (common ground point) |

Current path: `panel + → VIN+ → [shunt on breakout] → VIN− → load resistor → panel − → common GND`

## Critical rules

1. **Raspberry Pi power is separate.** Power the Pi through its normal 5 V
   micro-USB supply. Do NOT power the Pi from the solar panel or from the INA219.
2. **No panel voltage on GPIO.** The only Pi ↔ INA219 connections are 3.3 V,
   GND, SDA, SCL. Panel voltage (VIN+, up to ~6–9 V) never touches a GPIO pin.
3. **Common ground is required.** Pi GND, INA219 GND, and the panel negative
   return must all be the same node so current has a return path and the shunt
   voltage is measured against a common reference.
4. **Current direction.** With the panel connected as above, current flows
   VIN+ → VIN− and the INA219 reports **positive** current. If you swap panel +
   and panel −, current reads negative (the INA219 supports bidirectional
   current, but the polarity tells you the wiring is reversed relative to the
   intended direction).
5. **Bus voltage vs shunt voltage.**
   - Bus voltage = voltage between VIN+ and GND ≈ panel terminal voltage.
   - Shunt voltage = V(VIN+) − V(VIN−) = the tiny voltage dropped across the
     0.1 Ω (typical) shunt.
   - Current = shunt_voltage / shunt_resistance.
   - Power = bus_voltage × current.
