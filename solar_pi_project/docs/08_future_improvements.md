# Future improvements

These are optional upgrades for a second phase of the project. None are
required for the base monitor.

## Sunlight intensity (BH1750)
- Connect a BH1750 light-intensity sensor over I²C (it also uses bus 1; check
  its address, typically 0x23 or 0x5C).
- Report lux on the dashboard alongside panel output.
- **Important:** lux measures perceived brightness, not solar irradiance
  (W/m²). Use lux only as a relative "sunny / cloudy" indicator unless you
  characterize the sensor against a pyranometer (see docs/06, §7).

## Panel temperature (DS18B20)
- Connect a waterproof DS18B20 (1-Wire) to the panel's back or frame.
- Enable 1-Wire on the Pi (`dtoverlay=w1-gpio`) and read temperature.
- Correlate temperature with voltage/efficiency: panels lose a small fraction
  of output per degree Celsius above 25 °C.

## Additional load options
- Add a selector (rotary switch or relays) among 22 Ω / 47 Ω / 100 Ω loads to
  trace the panel's I–V curve at fixed points.
- **Safety:** each load must be rated for the power it will dissipate and kept
  away from flammable materials.

## Maximum-power-point tracking (MPPT) experiment
- A fixed resistor is not MPPT (see docs/06). As an experiment, use a PWM
  buck converter or a programmable electronic load controlled by the Pi to
  sweep the load and find the point of maximum power under different light
  levels. Log MPPT vs fixed-resistor power to quantify the difference.
- This is an advanced electronics extension; start with the fixed-resistor
  monitor working reliably first.

## Enclosure and mounting
- House the Pi and breakout in a project box.
- Mount the panel at a fixed tilt facing the sun; record the angle so results
  are reproducible.
- Keep the 5 W resistor ventilated and away from plastic/enclosure walls.

## Data & connectivity
- Add Wi-Fi signal strength display, uptime, and free disk space to the
  dashboard.
- Export to USB or a network share for long-term logs.
- Add user authentication if the Pi is on a network with untrusted devices.
