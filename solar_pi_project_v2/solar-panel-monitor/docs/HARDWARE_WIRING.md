# Hardware Wiring — Solar Panel + INA219 + Raspberry Pi 3 Model A+

**WARNING: Perform all wiring with the Raspberry Pi powered OFF and the solar panel
disconnected. Double-check every connection before applying power.**

## Proposed connections

| INA219 pin | Raspberry Pi physical pin | Pi function |
|------------|---------------------------|-------------|
| VCC        | Pin 1                     | 3.3 V       |
| GND        | Pin 6                     | GND         |
| SDA        | Pin 3                     | GPIO 2 (SDA)|
| SCL        | Pin 5                     | GPIO 3 (SCL)|

## Measurement path (power side)

```
Solar panel (+) ──► INA219 VIN+ ──► [shunt] ──► INA219 VIN− ──► 33 Ω 2 W resistor ──► Solar panel (−)
                                                  │
                                                  └─ (shunt voltage measured across VIN+/VIN−)
```

The INA219 measures the shunt voltage between VIN+ and VIN−, so the 33 Ω load
resistor goes **after** VIN− on the return path to solar negative.

## Critical safety precautions

1. **Power the Pi separately** through its 5 V micro-USB input. Never power the
   Pi through the INA219 measurement terminals.
2. **Never apply solar-panel voltage directly to a Pi GPIO.** The INA219 talks
   to the Pi over I²C at 3.3 V only; the panel voltage stays on the sensor's
   VIN+/VIN− side.
3. **Verify the panel's open-circuit voltage** with a multimeter before
   connecting. The 6 V, 3 W panel's Voc is typically ~7–9 V in bright sun —
   well within the INA219's common-mode range (0–26 V for most breakouts),
   but confirm your breakout's rating.
4. **Check the shunt rating** on your actual breakout board. The INA219's
   full-scale shunt voltage is typically ±320 mV. With a 0.1 Ω shunt that is
   ±3.2 A; with your 33 Ω load at 6 V the current is ~180 mA, well within
   range. Confirm your breakout's shunt value (many modules use 0.1 Ω).
5. **Resistor dissipation:** P = I²R ≈ (0.18 A)² × 33 Ω ≈ 1.1 W — under the
   2 W resistor rating. In full sun, measure actual current and confirm you
   stay below 2 W.
6. **Address pins (A0/A1):** Do not connect A0/A1 without verifying your
   breakout's documentation. Modules differ; the I²C address is commonly 0x40
   but may be 0x41–0x47 depending on A0/A1. Run `sudo i2cdetect -y 1` with
   I²C enabled to confirm the actual address, then update `config.json` /
   `.env` (`INA219_I2C_ADDRESS`).
7. **Grounding:** Confirm whether your breakout ties sensor GND to Pi GND or
   isolates the measurement side. Verify against the breakout schematic before
   finalizing ground connections.

## Multimeter verification checklist (power OFF)

- [ ] Panel Voc measured (expect ~7–9 V open circuit).
- [ ] INA219 VCC reads 3.3 V from the Pi once powered.
- [ ] INA219 GND and Pi GND are common (or isolation is intentional).
- [ ] SDA/SCL are not shorted to VCC or GND.
- [ ] 33 Ω resistor reads ~33 Ω.
- [ ] I²C address detected by `sudo i2cdetect -y 1` matches `INA219_I2C_ADDRESS`.

## Power-on procedure

1. Wire everything with the Pi unplugged and the panel covered/disconnected.
2. Connect the Pi to its separate 5 V micro-USB supply and boot.
3. Enable I²C (`sudo raspi-config` → Interface Options → I2C → Yes) and reboot.
4. Run `sudo i2cdetect -y 1` — the INA219 should appear at its address.
5. Run `python scripts/check_hardware.py` to confirm a reading.
6. Only then connect the solar panel (start covered, then expose to light).

## What to verify after power-on

- Bus voltage near the panel voltage under load.
- Current positive when the panel is illuminated and the circuit is closed.
- Power ≈ voltage × current.
- Covering the panel drops current/power toward zero.
