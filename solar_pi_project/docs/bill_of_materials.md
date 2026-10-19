# Solar Panel Performance Monitor - Bill of Materials

## Core Components

| Item                                      | Quantity | Description                                                                 |
|-------------------------------------------|----------|-----------------------------------------------------------------------------|
| Raspberry Pi 3 Model A+                   | 1        | ARM Cortex-A53 1.4GHz, 512MB RAM, no Ethernet (uses Wi-Fi)                 |
| INA219 bidirectional current/power module | 1        | 8-pin module with I²C interface, ±3.2A shunt range (default)                |
| Solar panel                               | 1        | ~6 V, 3 W (unloaded voltage should be checked; must be within INA219 range)|
| 22 Ω, 5 W wirewound power resistor        | 1        | Test load for solar panel                                                   |
| Breadboard                                | 1        | For prototyping connections                                                |
| Male-to-male jumper wires                 | Assorted | For breadboard interconnections                                            |
| Insulated connecting wires                | Assorted | For permanent or semi-permanent connections                                |
| microSD card                              | 1        | minimum 8GB, Raspberry Pi OS installed                                     |
| 5 V micro-USB power supply                | 1        | Stable power source for Raspberry Pi (≥ 2.5 A recommended)                |
| Multimeter                                | 1        | For verification of voltages and currents                                    |
| USB-C or micro-USB cable                  | 1        | For Pi OS installation and power                                           |

## Optional Components (Future Upgrades)

| Item                                      | Quantity | Description               |
|-------------------------------------------|----------|---------------------------|
| BH1750 light intensity sensor             | 1        | I²C, lux measurement       |
| DS18B20 temperature sensor                | 1        | 1-Wire, ±0.5°C accuracy    |
| Enclosure / mounting hardware             | 1 set    | Weatherproof or desktop     |

## Equipment / Tools

| Item          | Purpose                     |
|---------------|-----------------------------|
| Screwdriver   | If resistor leads need bending |
| Wire strippers| Preparing jumper wires       |
| Helping hands | Holding components           |

## Notes on Component Selection

- The INA219 breakout board has a typical shunt resistor of 0.1 Ω, giving a full-scale
  current range of ±3.2 A. For a 3 W / 6 V panel, expect short-circuit current of ~500 mA,
  well within the module's range.
- The 22 Ω / 5 W resistor is a test load; its power rating ensures it can dissipate
  the panel's full output (3 W) without overheating.
- Always verify the solar panel's open-circuit voltage before connecting to the INA219.
  The INA219 VBus range is typically 0–32 V, but check the specific module variant.