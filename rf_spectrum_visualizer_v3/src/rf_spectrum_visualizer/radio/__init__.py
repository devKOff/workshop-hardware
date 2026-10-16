"""Radio adapters for RF Spectrum Visualizer V3.

Provides HardwareRadio and SimRadio interfaces used by the ScannerService
and GUI tools. HardwareRadio checks for pyrf24 availability and gracefully
falls back to simulation. SimRadio uses the V6 richer simulation with
deterministic scenarios.

Key design decisions:
- HardwareRadio adapter wraps V3/V6 HardwareRadio with pyrf24 availability check.
- Simulation Radio uses V6's SimRadio with deterministic scenarios.
- Backend ("hardware" or "sim") is shared across all three GUI tools.
- Safe fallback: if pyrf24 is not installed, automatically use simulation.
- All measurements clearly labeled with source (hardware/sim).
"""

import logging
from typing import Optional, Any

logger = logging.getLogger("rf_visualizer.radio")

# Lazy imports to avoid pyrf24 dependency at module load time
_hardware_radio_imported = False
_sim_radio_imported = False


def is_hardware_available() -> bool:
    """Check if pyrf24 hardware backend is available.

    Returns:
        True if pyrf24 is installed and SPI devices are accessible.
    """
    try:
        import pyrf24
        return True
    except ImportError:
        return False


class HardwareRadioAdapter:
    """Adapter for hardware nRF24L01+ radio via pyrf24.

    Wraps the HardwareRadio from source projects with availability checking
    and graceful fallback messaging. Designed for environments without
    Raspberry Pi hardware.

    The adapter checks pyrf24 availability on initialization and raises
    ScannerError if hardware is not available, allowing the ScannerService
    to fall back to simulation.
    """

    def __init__(self, channel_config: Any, scan_config: Any,
                 hardware_config: Optional[Any] = None):
        """Initialize the hardware radio adapter.

        Args:
            channel_config: ChannelConfig with start_channel and end_channel.
            scan_config: ScanConfig with measurement_window and sampling_interval.
            hardware_config: Optional HardwareConfig with ce_pin, csn_pin, spi_speed.

        Raises:
            ScannerError: If pyrf24 is not installed.
        """
        from ..exceptions import ScannerError

        if not is_hardware_available():
            raise ScannerError(
                "Hardware backend not available (pyrf24 not installed. "
                "Install with: pip install pyrf24. "
                "For Raspberry Pi: sudo apt install python3-spidev python3-dev, "
                "then pip install pyrf24). "
                "Simulation mode will be used instead."
            )

        # Import HardwareRadio from v6 (original source, not modified)
        from v6.hardware_radio import HardwareRadio as V6HardwareRadio  # type: ignore
        from v6.config import HardwareConfig

        if hardware_config is None:
            hardware_config = HardwareConfig()

        self._radio = V6HardwareRadio(channel_config, scan_config, hardware_config)
        self._initialized = self._radio.is_initialized()
        logger.info(f"HardwareRadio adapter initialized (available: {self._initialized})")

    def is_available(self) -> bool:
        """Check if hardware backend is available."""
        return is_hardware_available()

    def initialize(self) -> bool:
        """Initialize the hardware radio."""
        if not self._initialized:
            try:
                self._radio.initialize()
                self._initialized = self._radio.is_initialized()
                logger.info(f"Hardware radio initialized on channel {self._radio.get_channel()}")
            except Exception as e:
                logger.error(f"Hardware radio initialization failed: {e}")
                self._initialized = False
        return self._initialized

    def is_initialized(self) -> bool:
        """Check if radio is initialized."""
        return self._initialized

    def set_channel(self, channel: int) -> None:
        """Set the radio channel."""
        if not self._initialized:
            raise Exception("Radio not initialized")
        self._radio.set_channel(channel)

    def get_channel(self) -> int:
        """Get the current channel."""
        if self._radio is not None:
            return self._radio.get_channel()
        return 0

    def read_rpd(self) -> bool:
        """Read RPD (Received Power Detector) status."""
        if self._radio is not None:
            return self._radio.read_rpd()
        return False

    def scan_channel(self, channel: int, duration: Optional[float] = None,
                     interval: Optional[float] = None) -> tuple:
        """Scan a channel for RPD activity.

        Returns:
            Tuple of (valid_samples, rpd_positive, rpd_negative)
        """
        if self._radio is not None:
            return self._radio.scan_channel(channel, duration, interval)
        return (0, 0, 0)

    def cleanup(self) -> None:
        """Clean up radio resources."""
        if self._radio is not None:
            self._radio.cleanup()
            self._initialized = False
        logger.info("HardwareRadioAdapter cleanup complete")


class SimRadioAdapter:
    """Adapter for simulated nRF24L01+ radio.

    Uses V6's SimRadio with deterministic scenarios for development and
    testing without physical hardware. Supports all 126 channels (0-125).

    The simulator generates deterministic data when a seed is provided, making
    it suitable for reproducible testing. All measurements are clearly labeled
    as simulated data.
    """

    def __init__(self, channel_config: Any, scan_config: Any,
                 sim_config: Optional[Any] = None, scenario: str = "mixed"):
        """Initialize the simulation radio adapter.

        Args:
            channel_config: ChannelConfig with start_channel and end_channel.
            scan_config: ScanConfig with measurement_window and sampling_interval.
            sim_config: Optional SimConfig with seed and deterministic flag.
            scenario: Scenario type string (e.g., "mixed", "quiet", "high_activity",
                      "wifi_like", "frequency_hopping", etc.).
        """
        from v6.sim_radio import SimRadio as V6SimRadio  # type: ignore
        from v6.scenario import ScenarioType  # type: ignore

        # Parse scenario string to ScenarioType enum
        if isinstance(scenario, ScenarioType):
            scenario_type = scenario
        else:
            try:
                scenario_type = ScenarioType(scenario)
            except ValueError:
                scenario_type = ScenarioType.MIXED
                logger.warning(f"Unknown scenario '{scenario}', defaulting to MIXED")

        # Create SimRadio with the specified scenario
        self._radio = V6SimRadio(
            channel_config,
            scan_config,
            sim_config=sim_config,
            scenario=scenario_type,
        )
        self._initialized = self._radio.initialize()
        logger.info(f"SimRadio adapter initialized with scenario='{scenario_type.value}'")

    def is_initialized(self) -> bool:
        """Check if radio is initialized."""
        return self._initialized

    def set_channel(self, channel: int) -> None:
        """Set the current channel."""
        if self._initialized and self._radio is not None:
            self._radio.set_channel(channel)

    def get_channel(self) -> int:
        """Get the current channel."""
        if self._radio is not None and self._initialized:
            return self._radio.get_channel()
        return 0

    def read_rpd(self) -> bool:
        """Read RPD (Received Power Detector) status."""
        if self._radio is not None and self._initialized:
            return self._radio.read_rpd()
        return False

    def scan_channel(self, channel: int, duration: Optional[float] = None,
                     interval: Optional[float] = None) -> tuple:
        """Scan a channel for RPD activity.

        Returns:
            Tuple of (valid_samples, rpd_positive, rpd_negative)
        """
        if self._radio is not None and self._initialized:
            return self._radio.scan_channel(channel, duration, interval)
        return (0, 0, 0)

    def cleanup(self) -> None:
        """Clean up radio resources."""
        if self._radio is not None:
            self._radio.cleanup()
            self._initialized = False
        logger.info("SimRadioAdapter cleanup complete")

    def get_channel_model(self, channel: int) -> Any:
        """Get the channel model for inspection.

        Args:
            channel: Channel number (0-125).

        Returns:
            ChannelModel object or None if channel not found.
        """
        if self._radio is not None and self._initialized:
            return self._radio.get_channel_model(channel)
        return None

    def get_simulated_time(self) -> float:
        """Get current simulated time."""
        if self._radio is not None and self._initialized:
            return self._radio.get_simulated_time()
        return 0.0

    def get_scenario_info(self) -> dict:
        """Get information about current scenario."""
        if self._radio is not None and self._initialized:
            return self._radio.get_scenario_info()
        return {"scenario": "unknown", "deterministic": False}