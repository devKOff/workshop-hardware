#!/usr/bin/env python3
"""
Solar Panel Performance Monitor - Sensor Reader

Reads voltage, current, and power from the INA219 module,
calculates energy, and logs readings to a SQLite database.

Features:
- INA219 voltage/current/power reading with error handling
- Energy integration (watt-hours) over elapsed time
- Daily energy total tracking with midnight reset
- SQLite database logging with timestamped records
- CSV export functionality
- Configurable sampling interval
"""

import time
import sqlite3
import os
import sys
from datetime import datetime, date
from collections import deque
from typing import Optional, Tuple, Dict, Any, List

try:
    from ina219 import INA219
    from ina219 import constants
    HAS_INA219 = True
except ImportError:
    HAS_INA219 = False
    print("WARNING: ina219 library not found. Install with: pip install ina219")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# INA219 configuration
DEFAULT_I2C_BUS = 1
DEFAULT_I2C_ADDRESS = 0x40  # A0=0, A1=0

# Gain setting: ±100 mV shunt range is good for small solar currents (~500 mA max)
# with the INA219's default 0.1 Ω shunt resistor.
DEFAULT_GAIN = constants.GAIN_1_4

# ADC resolution: 12-bit, 128 samples for good noise rejection
DEFAULT_ADC_RESOLUTION = constants.ADC_RESOLUTION_12BIT_128S

# Shunt resistor value in ohms (check your INA219 breakout)
# The default breakout board uses a 0.1 Ω shunt resistor.
SHUNT_RESISTOR_OHMS = 0.1

# Sampling interval in seconds (1 Hz = once per second)
SAMPLING_INTERVAL = 1.0

# Energy calculation: integrate power over time
# Energy (Wh) = Σ power(W) × interval(s) / 3600

# Database path
DEFAULT_DB_PATH = os.path.expanduser("~/solar_monitor/data/solar_readings.db")

# Historical data retention (keep last N readings in memory)
HISTORY_SIZE = 1000  # ~28 hours at 1-second sampling


# ---------------------------------------------------------------------------
# Sensor Wrapper
# ---------------------------------------------------------------------------

class IN219Sensor:
    """
    Wrapper for the INA219 sensor with error handling, configuration,
    and energy integration support.
    """

    def __init__(
        self,
        i2c_bus: int = DEFAULT_I2C_BUS,
        i2c_address: int = DEFAULT_I2C_ADDRESS,
        gain: int = DEFAULT_GAIN,
        adc_resolution: int = DEFAULT_ADC_RESOLUTION,
        shunt_resistor_ohms: float = SHUNT_RESISTOR_OHMS,
    ):
        self.shunt_resistor_ohms = shunt_resistor_ohms
        self.last_reading_time: Optional[float] = None
        self.accumulated_energy_wh: float = 0.0
        self.daily_energy_wh: float = 0.0
        self.last_date: Optional[date] = None
        self.reading_count: int = 0

        if not HAS_INA219:
            raise RuntimeError("INA219 library not available")

        try:
            self.sensor = INA219(
                bus=i2c_bus,
                address=i2c_address,
                gain=gain,
                adc_resolution=adc_resolution,
            )
            # Apply the shunt resistor value for current calculation
            self.sensor.shunt_resistor = shunt_resistor_ohms

            # Configure gain after initialization (some boards require this)
            self.sensor.gain = gain

            # Configure ADC resolution
            self.sensor.bus_adc_resolution = adc_resolution
            self.sensor.shunt_adc_resolution = adc_resolution

            # Initialize accumulated energy
            self.accumulated_energy_wh = 0.0
            self.daily_energy_wh = 0.0
            self.last_date = date.today()

            print(f"INA219 initialized at address 0x{i2c_address:02X}")
            print(f"  Gain: {gain}")
            print(f"  ADC Resolution: {adc_resolution}")
            print(f"  Shunt resistor: {shunt_resistor_ohms} Ω")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize INA219: {e}")

    # -----------------------------------------------------------------------
    # Raw reading methods
    # -----------------------------------------------------------------------

    def read_bus_voltage(self) -> Optional[float]:
        """Read bus voltage in volts (V). Returns None on error."""
        try:
            voltage = self.sensor.voltage()
            return round(voltage, 2) if voltage is not None else None
        except Exception as e:
            print(f"Error reading bus voltage: {e}")
            return None

    def read_shunt_voltage(self) -> Optional[float]:
        """Read shunt voltage in millivolts (mV). Returns None on error."""
        try:
            voltage = self.sensor.shunt_voltage()
            return round(voltage, 2) if voltage is not None else None
        except Exception as e:
            print(f"Error reading shunt voltage: {e}")
            return None

    def read_current(self) -> Optional[float]:
        """
        Read current in milliamps (mA).
        Positive = current flowing from VIN+ to VIN- (panel supplying load).
        Negative = current flowing from VIN- to VIN+ (e.g., battery charging).
        Returns None on error.
        """
        try:
            current = self.sensor.current()
            return round(current, 2) if current is not None else None
        except Exception as e:
            print(f"Error reading current: {e}")
            return None

    def read_power(self) -> Optional[float]:
        """Read instantaneous power in watts (W). Returns None on error."""
        try:
            power = self.sensor.power()
            return round(power, 2) if power is not None else None
        except Exception as e:
            print(f"Error reading power: {e}")
            return None

    # -----------------------------------------------------------------------
    # Unified reading
    # -----------------------------------------------------------------------

    def read_all(self) -> Dict[str, Optional[float]]:
        """
        Read all parameters (voltage, current, power, shunt voltage) in one call.
        Returns a dict with keys: 'timestamp', 'voltage_V', 'current_mA',
        'power_W', 'shunt_mV'.
        """
        timestamp = time.time()
        voltage = self.read_bus_voltage()
        current = self.read_current()
        power = self.read_power()
        shunt = self.read_shunt_voltage()

        return {
            "timestamp": timestamp,
            "voltage_V": voltage,
            "current_mA": current,
            "power_W": power,
            "shunt_mV": shunt,
        }

    # -----------------------------------------------------------------------
    # Energy integration
    # -----------------------------------------------------------------------

    def update_energy(self, reading: Dict[str, Optional[float]]) -> Tuple[float, float]:
        """
        Update accumulated and daily energy based on a new reading.

        The energy integration uses the trapezoidal rule:
        ΔE = (P_prev + P_current) / 2 × Δt / 3600  (in watt-hours)

        Returns (accumulated_energy_wh, daily_energy_wh).
        """
        current_time = time.time()
        current_date = date.fromtimestamp(current_time)

        # Check if we've crossed a midnight boundary
        if self.last_date is not None and current_date != self.last_date:
            # New day — reset daily total but keep accumulated
            print(f"New day detected ({current_date}), resetting daily energy total")
            self.daily_energy_wh = 0.0

        self.last_date = current_date

        # If this is the second or later reading, integrate
        if self.last_reading_time is not None and reading.get("power_W") is not None:
            prev_power = self._last_power_W
            curr_power = reading["power_W"]
            dt = current_time - self.last_reading_time  # in seconds

            # Guard against unreasonable time intervals (e.g., clock sync jump)
            if 0 < dt < 60:  # max 60 s to avoid huge integrals
                # Trapezoidal integration: average power × time / 3600 → Wh
                energy_wh = ((prev_power + curr_power) / 2.0) * dt / 3600.0
                self.accumulated_energy_wh += energy_wh
                self.daily_energy_wh += energy_wh
            else:
                print(f"Skipping energy integration: dt={dt:.2f}s (last_power={prev_power}, "
                      f"curr_power={curr_power})")

        # Store current power for next iteration
        self._last_power_W = reading.get("power_W")

        return self.accumulated_energy_wh, self.daily_energy_wh

    # -----------------------------------------------------------------------
    # Date/day helpers
    # -----------------------------------------------------------------------

    def get_daily_total(self) -> float:
        """Return the daily energy total in watt-hours."""
        return round(self.daily_energy_wh, 2)

    def get_accumulated_total(self) -> float:
        """Return the accumulated energy total in watt-hours."""
        return round(self.accumulated_energy_wh, 2)

    def get_accumulated_and_daily(self) -> Tuple[float, float]:
        """Return (accumulated_energy_Wh, daily_energy_Wh)."""
        return (self.accumulated_energy_wh, self.daily_energy_wh)

    def reset_daily(self):
        """Manually reset the daily energy total (e.g., for testing)."""
        self.daily_energy_wh = 0.0
        self.last_date = date.today()
        print("Daily energy total manually reset")

    # -----------------------------------------------------------------------
    # Read with error handling / fallback values
    # -----------------------------------------------------------------------

    def safe_read_all(self) -> Dict[str, Any]:
        """
        Read all sensor values with error handling.
        Returns a dict with readings and a 'status' flag.
        If a read fails, the value is None and status is 'error'.
        """
        reading = self.read_all()

        # Check for valid readings
        status = "ok"
        if reading["voltage_V"] is None:
            status = "voltage_error"
        elif reading["current_mA"] is None:
            status = "current_error"
        elif reading["power_W"] is None:
            status = "power_error"

        result = {
            "status": status,
            "timestamp": datetime.fromtimestamp(reading["timestamp"]).isoformat()
            if reading["timestamp"] else None,
            "voltage_V": reading["voltage_V"],
            "current_mA": reading["current_mA"],
            "power_W": reading["power_W"],
            "shunt_mV": reading["shunt_mV"],
        }
        return result


# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------

class ReadingDatabase:
    """
    SQLite database manager for timestamped solar readings.
    Supports logging, querying, and CSV export.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_directory()
        self._create_table()
        print(f"Database ready at: {self.db_path}")

    def _ensure_directory(self):
        """Create the directory for the database if it doesn't exist."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _create_table(self):
        """Create the readings table if it doesn't exist."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            date TEXT NOT NULL,
            time_text TEXT NOT NULL,
            voltage_V REAL,
            current_mA REAL,
            power_W REAL,
            shunt_mV REAL,
            accumulated_Wh REAL,
            daily_Wh REAL
        );
        """
        with self._get_connection() as conn:
            conn.execute(create_sql)
        # Create indexes for faster queries
        with self._get_connection() as conn:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_date ON readings(date);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON readings(timestamp);"
            )

    def _get_connection(self):
        """Context manager for a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def log_reading(self, reading: Dict[str, Any]) -> Optional[int]:
        """
        Log a single reading to the database.
        Returns the row ID, or None on error.
        """
        try:
            date_val = reading.get("timestamp")
            if isinstance(date_val, float):
                dt = datetime.fromtimestamp(date_val)
            else:
                dt = datetime.now()

            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M:%S")

            sql = """
            INSERT INTO readings
                (timestamp, date, time_text, voltage_V, current_mA, power_W,
                 shunt_mV, accumulated_Wh, daily_Wh)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            with self._get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (
                        dt.isoformat(),
                        date_str,
                        time_str,
                        reading.get("voltage_V"),
                        reading.get("current_mA"),
                        reading.get("power_W"),
                        reading.get("shunt_mV"),
                        reading.get("accumulated_Wh"),
                        reading.get("daily_Wh"),
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error logging reading to database: {e}")
            return None

    def get_readings_by_date(self, target_date: date) -> List[Dict[str, Any]]:
        """Retrieve all readings for a specific date."""
        sql = """
        SELECT * FROM readings
        WHERE date = ?
        ORDER BY timestamp ASC
        """
        with self._get_connection() as conn:
            conn.execute(sql, (target_date.isoformat(),))
            rows = conn.fetchall()

        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "date": row["date"],
                    "time_text": row["time_text"],
                    "voltage_V": row["voltage_V"],
                    "current_mA": row["current_mA"],
                    "power_W": row["power_W"],
                    "shunt_mV": row["shunt_mV"],
                    "accumulated_Wh": row["accumulated_Wh"],
                    "daily_Wh": row["daily_Wh"],
                }
            )
        return result

    def get_all_readings(self) -> List[Dict[str, Any]]:
        """Retrieve all stored readings."""
        sql = "SELECT * FROM readings ORDER BY timestamp ASC"
        with self._get_connection() as conn:
            conn.execute(sql)
            rows = conn.fetchall()

        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "date": row["date"],
                    "time_text": row["time_text"],
                    "voltage_V": row["voltage_V"],
                    "current_mA": row["current_mA"],
                    "power_W": row["power_W"],
                    "shunt_mV": row["shunt_mV"],
                    "accumulated_Wh": row["accumulated_Wh"],
                    "daily_Wh": row["daily_Wh"],
                }
            )
        return result

    def get_readings_range(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Retrieve readings within a date range (inclusive)."""
        sql = """
        SELECT * FROM readings
        WHERE date >= ? AND date <= ?
        ORDER BY timestamp ASC
        """
        with self._get_connection() as conn:
            conn.execute(sql, (start_date.isoformat(), end_date.isoformat()))
            rows = conn.fetchall()

        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "date": row["date"],
                    "time_text": row["time_text"],
                    "voltage_V": row["voltage_V"],
                    "current_mA": row["current_mA"],
                    "power_W": row["power_W"],
                    "shunt_mV": row["shunt_mV"],
                    "accumulated_Wh": row["accumulated_Wh"],
                    "daily_Wh": row["daily_Wh"],
                }
            )
        return result

    def export_csv(self, filepath: Optional[str] = None, date_filter: Optional[date] = None) -> str:
        """
        Export readings to a CSV file.
        If date_filter is provided, only export readings for that date.
        Returns the filepath of the created CSV.
        """
        if filepath is None:
            today_str = date.today().strftime("%Y-%m-%d")
            filepath = os.path.expanduser(
                f"~/solar_monitor/exports/solar_readings_{today_str}.csv"
            )

        # Ensure the export directory exists
        export_dir = os.path.dirname(filepath)
        if export_dir and not os.path.exists(export_dir):
            os.makedirs(export_dir, exist_ok=True)

        # Determine which readings to export
        if date_filter is not None:
            readings = self.get_readings_by_date(date_filter)
        else:
            readings = self.get_all_readings()

        import csv
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            # Header
            writer.writerow(
                [
                    "ID",
                    "Timestamp",
                    "Date",
                    "Time",
                    "Voltage_V",
                    "Current_mA",
                    "Power_W",
                    "Shunt_mV",
                    "Accumulated_Wh",
                    "Daily_Wh",
                ]
            )
            # Data rows
            for row in readings:
                writer.writerow(
                    [
                        row["id"],
                        row["timestamp"],
                        row["date"],
                        row["time_text"],
                        row["voltage_V"],
                        row["current_mA"],
                        row["power_W"],
                        row["shunt_mV"],
                        row["accumulated_Wh"],
                        row["daily_Wh"],
                    ]
                )

        print(f"Exported {len(readings)} readings to {filepath}")
        return filepath

    def get_count(self) -> int:
        """Return the total number of stored readings."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM readings")
            return cursor.fetchone()[0]

    def get_daily_summary(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Return a summary of readings for a given date."""
        if target_date is None:
            target_date = date.today()

        readings = self.get_readings_by_date(target_date)

        if not readings:
            return {
                "date": target_date.isoformat(),
                "reading_count": 0,
                "total_energy_Wh": 0.0,
                "avg_voltage_V": 0.0,
                "avg_current_mA": 0.0,
                "avg_power_W": 0.0,
                "first_reading": None,
                "last_reading": None,
            }

        voltages = [r["voltage_V"] for r in readings if r["voltage_V"] is not None]
        currents = [r["current_mA"] for r in readings if r["current_mA"] is not None]
        powers = [r["power_W"] for r in readings if r["power_W"] is not None]

        first = readings[0]
        last = readings[-1]

        summary = {
            "date": target_date.isoformat(),
            "reading_count": len(readings),
            "total_energy_Wh": round(sum(powers), 2) if powers else 0.0,
            "avg_voltage_V": round(sum(voltages) / len(voltages), 2) if voltages else 0.0,
            "avg_current_mA": round(sum(currents) / len(currents), 2) if currents else 0.0,
            "avg_power_W": round(sum(powers) / len(powers), 2) if powers else 0.0,
            "first_reading_time": first["time_text"],
            "last_reading_time": last["time_text"],
            "min_voltage_V": round(min(voltages), 2) if voltages else 0.0,
            "max_voltage_V": round(max(voltages), 2) if voltages else 0.0,
            "min_current_mA": round(min(currents), 2) if currents else 0.0,
            "max_current_mA": round(max(currents), 2) if currents else 0.0,
            "min_power_W": round(min(powers), 2) if powers else 0.0,
            "max_power_W": round(max(powers), 2) if powers else 0.0,
        }
        return summary


# ---------------------------------------------------------------------------
# Main Monitoring Loop
# ---------------------------------------------------------------------------

class SolarMonitor:
    """
    Main monitoring class that ties the sensor, energy integration,
    and database logging together.
    """

    def __init__(
        self,
        sensor: IN219Sensor,
        database: ReadingDatabase,
        sampling_interval: float = SAMPLING_INTERVAL,
        history_size: int = HISTORY_SIZE,
    ):
        self.sensor = sensor
        self.database = database
        self.sampling_interval = sampling_interval
        self.running = False

        # Historical data in memory (for real-time display / graphs)
        # Each entry: (timestamp, voltage, current, power, accumulated, daily)
        self.history = deque(maxlen=history_size)

        # Track the last logged accumulated/daily energy values
        # to avoid logging the same updated values repeatedly
        self.last_logged_accumulated = 0.0
        self.last_logged_daily = 0.0

    def start(self):
        """Start the monitoring loop."""
        self.running = True
        print(f"Starting solar monitor with {self.sampling_interval}s sampling interval")
        print("Press Ctrl+C to stop")

        try:
            self._monitor_loop()
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        finally:
            self.running = False
            # Final database sync
            self._final_sync()
            print("Monitoring loop ended")

    def _monitor_loop(self):
        """Internal loop that reads sensor, updates energy, and logs to database."""
        while self.running:
            start_time = time.time()

            # Read sensor values
            reading = self.sensor.safe_read_all()

            # Update energy integration
            accumulated, daily = self.sensor.update_energy(reading)

            # Add to history
            entry = (
                reading["timestamp"],
                reading["voltage_V"],
                reading["current_mA"],
                reading["power_W"],
                accumulated,
                daily,
            )
            self.history.append(entry)

            # Log to database (every few readings to avoid flooding)
            log_now = False
            if reading["power_W"] is not None:
                # Log at least once per minute, or if energy changed significantly
                if (
                    self.database.get_count() == 0
                    or accumulated - self.last_logged_accumulated >= 0.1
                    or daily - self.last_logged_daily >= 0.1
                ):
                    log_now = True

            if log_now:
                self.database.log_reading(
                    {
                        "timestamp": reading["timestamp"],
                        "voltage_V": reading["voltage_V"],
                        "current_mA": reading["current_mA"],
                        "power_W": reading["power_W"],
                        "shunt_mV": reading["shunt_mV"],
                        "accumulated_Wh": accumulated,
                        "daily_Wh": daily,
                    }
                )
                self.last_logged_accumulated = accumulated
                self.last_logged_daily = daily

            # Sleep for the remaining interval time
            elapsed = time.time() - start_time
            sleep_time = self.sampling_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _final_sync(self):
        """Ensure the last reading's energy values are saved."""
        if self.history:
            last_entry = self.history[-1]
            # Only sync if there are readings and values have changed
            accumulated = last_entry[4]
            daily = last_entry[5]
            if (
                abs(accumulated - self.last_logged_accumulated) > 0.01
                or abs(daily - self.last_logged_daily) > 0.01
            ):
                reading = {
                    "timestamp": last_entry[0],
                    "voltage_V": last_entry[1],
                    "current_mA": last_entry[2],
                    "power_W": last_entry[3],
                    "shunt_mV": None,
                    "accumulated_Wh": accumulated,
                    "daily_Wh": daily,
                }
                self.database.log_reading(reading)

    def get_history(self) -> List[Tuple]:
        """Return the historical readings as a list."""
        return list(self.history)

    def get_recent_history(
        self, minutes: int = 60
    ) -> List[Tuple]:
        """Return readings from the last N minutes."""
        if not self.history:
            return []
        cutoff_time = time.time() - (minutes * 60)
        return [entry for entry in self.history if entry[0] >= cutoff_time]

    def get_history_for_date(self, target_date: date) -> List[Tuple]:
        """Return history entries for a specific date."""
        if not self.history:
            return []
        return [
            entry
            for entry in self.history
            if date.fromtimestamp(entry[0]) == target_date
        ]


# ---------------------------------------------------------------------------
# Command-Line Test Utilities
# ---------------------------------------------------------------------------

def test_sensor():
    """Simple test function to verify the INA219 sensor is working."""
    from ina219 import constants

    # Initialize sensor (adjust parameters as needed for your setup)
    try:
        sensor = IN219Sensor(
            i2c_address=0x40,
            gain=constants.GAIN_1_4,
            adc_resolution=constants.ADC_RESOLUTION_12BIT_128S,
        )
    except RuntimeError as e:
        print(f"Could not initialize sensor: {e}")
        print("Check I²C wiring and I²C interface enablement.")
        return

    print("\n--- INA219 Sensor Test ---")
    print("Reading measurements (press Ctrl+C to stop)...")

    try:
        while True:
            reading = sensor.safe_read_all()
            now = datetime.now().strftime("%H:%M:%S")

            # Display readings
            voltage = reading["voltage_V"]
            current = reading["current_mA"]
            power = reading["power_W"]
            shunt = reading["shunt_mV"]
            status = reading["status"]

            # Format output
            parts = [f"[{now}]"]
            if voltage is not None:
                parts.append(f"V={voltage}V")
            if current is not None:
                parts.append(f"I={current}mA")
            if power is not None:
                parts.append(f"P={power}W")
            if shunt is not None:
                parts.append(f"Vsh={shunt}mV")
            if status != "ok":
                parts.append(f"(!{status})")

            print("  ".join(parts))

            # Update and display energy
            accumulated, daily = sensor.get_accumulated_and_daily()
            print(
                f"  Energy: Accumulated={accumulated} Wh, Daily={daily} Wh"
            )

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTest stopped.")


def get_example_calculations():
    """
    Provide example calculations using realistic values.
    These are NOT actual sensor readings, just illustrative examples.
    """
    print("\n--- Example Calculations (Illustrative Only) ---")

    # Example 1: Panel under load
    panel_voltage = 6.5  # V (open-circuit ~7-9 V, loaded lower)
    panel_current = 250  # mA (~0.25 A for a small 3 W panel)
    panel_power = panel_voltage * (panel_current / 1000)  # W

    print(f"Example 1 - Panel under typical load:")
    print(f"  Voltage: {panel_voltage} V")
    print(f"  Current: {panel_current} mA ({panel_current/1000:.3f} A)")
    print(f"  Power: {panel_power:.3f} W (={panel_voltage:.2f} × {panel_current/1000:.3f})")
    print()

    # Example 2: Energy over 1 hour
    power_w = 1.5  # W
    duration_s = 3600  # 1 hour
    energy_wh = power_w * duration_s / 3600  # Wh

    print(f"Example 2 - Energy over 1 hour at 1.5 W:")
    print(f"  Power: {power_w} W")
    print(f"  Duration: {duration_s // 60} minutes ({duration_s}s)")
    print(f"  Energy: {energy_wh:.2f} Wh (={power_w} × {duration_s}/3600)")
    print()

    # Example 3: Daily energy accumulation
    # Suppose we get a reading every second for 24 hours
    second_power = 1.5  # W (assumed constant for this example)
    readings_per_day = 60 * 60 * 24  # 86400 seconds
    total_energy_wh = second_power * readings_per_day / 3600  # Wh

    print(f"Example 3 - Daily energy if {second_power} W constant for 24 h:")
    print(f"  Readings per day: {readings_per_day}")
    print(f"  Total energy: {total_energy_wh:.2f} Wh")
    print(
        f"  (In practice, power varies throughout the day; this is a constant-power illustration)"
    )
    print()

    # Example 4: Trapezoidal integration between two readings
    power_prev = 1.2  # W
    power_curr = 1.8  # W
    dt = 1.0  # 1 second interval
    energy_increment_wh = ((power_prev + power_curr) / 2.0) * dt / 3600

    print(f"Example 4 - Trapezoidal energy increment between two 1-s readings:")
    print(f"  Previous power: {power_prev} W")
    print(f"  Current power: {power_curr} W")
    print(f"  Time interval: {dt} s")
    print(f"  Energy increment: {energy_increment_wh:.6f} Wh")
    print(f"  (=(1.2 + 1.8) / 2 × 1 / 3600)")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "examples":
        get_example_calculations()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        test_sensor()
    else:
        print("Usage: python sensor_reader.py [examples|test]")
        print("  examples - Show illustrative calculation examples")
        print("  test     - Run continuous sensor test")