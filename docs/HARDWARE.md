# Hardware Wiring Guide — INA219 on Raspberry Pi 3 Model A+

## Target hardware

- Raspberry Pi 3 Model A+
- INA219 voltage/current sensor breakout (I²C)
- 6 V, 3 W solar panel
- 33 Ω resistive load
- Separate regulated 5 V supply for the Raspberry Pi
- I²C communication between the Pi and INA219

## I²C connections

| INA219 pin | Raspberry Pi pin | Notes |
|------------|------------------|-------|
| VCC        | 3.3 V (pin 1)    | INA219 logic power |
| GND        | GND (pin 6, 9, 14, 20, 25, 30, 34, 39) | Common ground |
| SCL        | GPIO 3 / SCL (pin 5) | I²C clock |
| SDA        | GPIO 2 / SDA (pin 3) | I²C data |

## Solar panel + load connections

| Component | Connection |
|-----------|------------|
| Solar panel + | INA219 Vin+ |
| Solar panel − | INA219 Vin− |
| INA219 Vin− | One end of 33 Ω load |
| Other end of 33 Ω load | GND |
| I2C bus power | 3.3 V from Pi |

The INA219 measures:
- **Bus voltage (V):** voltage across Vin+ and Vin− (panel side)
- **Shunt voltage:** voltage across the internal shunt (current side)
- **Current:** derived from shunt voltage ÷ shunt resistance

## Calibration

The INA219 calibration register depends on your breakout board's shunt resistor:

    Cal = 4096 / (Max_Current × R_shunt)
    Current_LSB = Max_Current / 32767
    Power_LSB = 20 × Current_LSB

Default calibration in the code: shunt = 0.1 Ω, max current = 1.0 A.
This gives Current_LSB ≈ 30.5 µA, which is suitable for the 0–0.5 A
range of a 6 V, 3 W panel on a 33 Ω load (max ≈ 0.18 A).

If your breakout board uses a different shunt resistor, edit
`src/solar_monitor/backends/hardware.py`:
`DEFAULT_SHUNT_OHM` and `DEFAULT_MAX_CURRENT_A`, or pass them to
`INA219HardwareBackend(shunt_ohm=..., max_current_a=...)`.

## Power supply separation

The Raspberry Pi must be powered by a **separate regulated 5 V supply**,
not from the solar panel. The solar panel feeds only the INA219 Vin+
and the 33 Ω load. This prevents panel voltage fluctuations from
resetting the Pi.

## Enabling I²C

```bash
sudo raspi-config nonint do_i2c 0
sudo reboot
```

Then verify detection:
```bash
sudo i2cdetect -y 1
```
The INA219 should appear at address `0x40` (ADDR pin to GND) or `0x41` (ADDR pin to VCC).

## Selecting hardware mode

1. Wire the sensor and enable I²C (above).
2. Verify detection with `i2cdetect`.
3. Launch the app: `python main.py`.
4. Open **Settings** → **Operating mode** → **Hardware** → **Save**.
5. The header and **System Information** page will show hardware status.
6. If the INA219 is not detected, an honest error state is shown —
   simulated readings are never substituted.
