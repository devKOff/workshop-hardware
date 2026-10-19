# Solar Panel Performance Monitor

## Project Overview

A low-cost solar monitoring system built around a Raspberry Pi 3 Model A+ and an INA219
bidirectional current/power sensor module. The system measures solar panel voltage,
current, and power; calculates accumulated energy; and serves a web dashboard accessible
from any device on the same local network.

## Block Diagram

```
+---------------------+       +---------------------+       +---------------------+
|   Solar Panel (6V)  |------>|   INA219 Sensor     |------>|   Raspberry Pi 3 A+ |
|                     |       |  VIN+, VIN-         |       |  (I²C, GPIO, USB)   |
|                     |       |  SHUNT, V+          |       |                       |
|                     |       |  SDA, SCL           |       |   +----------------+   |
|                     |       |  GND                |       ->|   Web Dashboard  |   |
+---------------------+       +---------------------+       |   (Flask + Chart.js)|   |
        ^                           ^                           +----------------+   |
        |                           |                                   |           |
        |                           |                                   |           |
        |                           +----> Optional: BH1750 (light)    |           |
        |                           +----> Optional: DS18B20 (temp)   |           |
        |                                                                       |           |
        +-----------------------------------------------------------------------+-----------+
                                                                   Local SQLite DB
                                                                   (energy logging)
```

## Measured Parameters

| Parameter       | Unit     | Source             |
|-----------------|----------|--------------------|
| Panel Voltage   | V        | INA219 VBus        |
| Panel Current   | mA / A   | INA219 Shunt       |
| Instantaneous Power | W     | INA219 calculation |
| Accumulated Energy | Wh    | Power × time integral |
| Daily Energy    | Wh/day   | Reset at midnight  |

## Optional Upgrades

- BH1750 light intensity sensor (lux)
- DS18B20 1-Wire temperature sensor
- Maximum Power Point Tracking (MPPT) experiments
- Enclosure and weatherproof mounting

## Target Audience

College IoT coursework / hobbyist solar monitoring project.
Designed for reliable measurement, safe wiring, and reproducibility.