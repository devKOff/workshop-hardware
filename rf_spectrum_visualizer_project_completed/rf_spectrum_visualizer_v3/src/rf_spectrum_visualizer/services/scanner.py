"""Scanner service for RF Spectrum Visualizer V3.

Integrates V3's ScannerThread with hardware (HardwareRadio) and simulation
(SimRadio) adapters. Provides a single authoritative scanning service with
no duplicate workers, safe start/stop/shutdown, and thread-safe access to
measurements shared with analysis and blocker services.

Key design decisions:
- Single ScannerService instance across all three GUI tools.
- Backend can be changed (hardware <-> sim) only when scanner is stopped.
- Scanner state (running/stopped) is shared with blocklist and analysis services.
- Graceful fallback to simulation when pyrf24 is unavailable.
- All measurements clearly labeled with source (hardware/sim).
"""

import threading
import logging
import time
from typing import Optional, Callable, Any

from ..models.channel import channel_to_frequency, frequency_to_channel, validate_channel, get_all_channels
from ..models.channel import ALL_CHANNELS, CHANNEL_MIN, CHANNEL_MAX
from ..exceptions import (
    ScannerError, ScannerNotRunningError, ScannerAlreadyRunningError,
    InvalidChannelError, HardwareError, SimulationError,
)
from ..services.blocklist import BlocklistManager


logger = logging.getLogger("rf_visualizer.services.scanner")


class ScannerService:
    """Central scanning service managing spectrum scanning with hardware or simulation backend.

    Responsibilities:
    - Start/stop/scanning lifecycle management.
    - Thread-safe spectrum data collection.
    - Hardware (HardwareRadio) and simulation (SimRadio) adapter support.
    - No duplicate scanning workers.
    - Safe shutdown and cleanup.
    - Thread-safe results available to analysis and blocker services.

    The scanner uses a single ScannerThread instance. Backend changes are only
    permitted when the scanner is stopped. Results are stored in a shared
    SpectrumData instance accessible to all three GUI tools.
    """

    def __init__(
        self,
        config: Any,  # AppConfig-like object with channel, scan configs
        backend: str = "sim",
    ):
        """Initialize the scanner service.

        Args:
            config: Application configuration with channel and scan settings.
            backend: Initial backend ("sim" or "hardware"). Defaults to "sim"
                     for environments without pyrf24/spidev.
        """
        self._config = config
        self._backend = backend
        self._spectrum_data = None  # Set by GUI, shared across tools
        self._scanner_thread: Optional[Any] = None  # ScannerThread instance
        self._radio: Optional[Any] = None  # HardwareRadio or SimRadio instance
        self._lock = threading.RLock()
        self._running = False
        self._initialized = False

        # Lazy-import ScannerThread to avoid circular imports at module level
        from ..scanner import ScannerThread  # V3 scanner.ScannerThread

        self._scanner_thread_class = ScannerThread

    def set_spectrum_data(self, spectrum_data) -> None:
        """Set the shared SpectrumData instance.

        Args:
            spectrum_data: SpectrumData instance shared across GUI tools.
        """
        self._spectrum_data = spectrum_data

    def is_running(self) -> bool:
        """Check if the scanner is currently running."""
        with self._lock:
            return self._running

    def set_backend(self, backend: str) -> None:
        """Set the scanning backend.

        Only effective when the scanner is not running. When changed while
        stopped, the radio instance is recreated for the new backend.

        Args:
            backend: "sim" for simulation, "hardware" for nRF24L01+.

        Raises:
            ScannerError: If attempting to change backend while scanner is running.
        """
        with self._lock:
            if self._running:
                raise ScannerError("Cannot change backend while scanner is running")
            self._backend = backend
            # Reset radio instance; will be created on next start
            self._radio = None
            logger.info(f"Scanner backend set to {backend}")

    def get_backend(self) -> str:
        """Get the current scanning backend."""
        with self._lock:
            return self._backend

    def start(self) -> None:
        """Start the scanner thread.

        Creates the radio instance for the current backend, initializes it,
        and starts the background scanning thread.

        Raises:
            ScannerAlreadyRunningError: If the scanner is already running.
            ScannerError: If hardware backend is not available.
        """
        with self._lock:
            if self._running:
                raise ScannerAlreadyRunningError("Scanner is already running")

            # Create radio instance
            self._create_radio()

            # Initialize the radio
            try:
                if self._radio is not None:
                    if not self._radio.is_initialized():
                        self._radio.initialize()
            except Exception as e:
                logger.error(f"Failed to initialize radio: {e}")
                raise ScannerError(f"Failed to initialize radio: {e}") from e

            # Create ScannerThread
            self._scanner_thread = self._scanner_thread_class(
                self._config,
                self._spectrum_data,
                self._radio,
                on_observation=self._on_observation,
                on_error=self._on_scanner_error,
                on_scan_complete=self._on_scan_complete,
            )

            self._scanner_thread.start()
            self._running = True
            self._initialized = True
            logger.info(f"Scanner started with {self._backend} backend")

    def _create_radio(self) -> None:
        """Create the radio instance for the current backend."""
        from ..radio import HardwareRadio, SimRadio  # HardwareRadio (V3/V6), SimRadio (V6 richer scenarios)

        if self._backend == "sim":
            self._radio = SimRadio(
                self._config.channel,
                self._config.scan,
                sim_config=self._config.sim if hasattr(self._config, "sim") else None,
            )
        else:  # hardware
            if not HardwareRadio.is_available():
                raise ScannerError("Hardware backend not available (pyrf24 missing or SPI unavailable)")
            self._radio = HardwareRadio(
                self._config.channel,
                self._config.scan,
                hardware_config=self._config.hardware if hasattr(self._config, "hardware") else None,
            )

    def _on_observation(self, obs: Any) -> None:
        """Callback invoked when a channel observation is completed.

        Args:
            obs: ChannelObservation from the scanner thread.
        """
        if self._spectrum_data is not None:
            self._spectrum_data.update_observation(obs)

    def _on_scanner_error(self, error: Exception) -> None:
        """Callback invoked when the scanner encounters an error.

        Args:
            error: The exception that occurred.
        """
        logger.error(f"Scanner error: {error}")
        # Error already logged by scanner thread; optionally propagate

    def _on_scan_complete(self) -> None:
        """Callback invoked when a full scan cycle completes."""
        logger.debug("Scanner scan cycle complete")

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop the scanner thread.

        Sets the stop event and waits for the thread to exit. Performs
        radio cleanup.

        Args:
            timeout: Maximum time in seconds to wait for thread exit.

        Returns:
            True if scanner stopped within timeout, False if thread did not
            stop in time.
        """
        with self._lock:
            if not self._running:
                return True

            self._running = False

        # Signal the thread to stop
        if self._scanner_thread is not None:
            result = self._scanner_thread.stop(timeout=timeout)
        else:
            result = True

        # Clean up radio resources
        self._cleanup_radio()

        with self._lock:
            self._running = False
            # Don't reset _scanner_thread here; let it be garbage collected
            # or explicitly reset by caller if needed

        logger.info("Scanner stopped")
        return result

    def _cleanup_radio(self) -> None:
        """Clean up radio resources."""
        if self._radio is not None:
            try:
                self._radio.cleanup()
            except Exception as e:
                logger.warning(f"Error during radio cleanup: {e}")
            self._radio = None

    def shutdown(self, timeout: float = 2.0) -> None:
        """Force shutdown of the scanner.

        Calls stop(timeout) and ensures all state is cleared.

        Args:
            timeout: Maximum time in seconds to wait for thread exit.
        """
        self.stop(timeout=timeout)
        with self._lock:
            self._running = False
            self._initialized = False
            self._scanner_thread = None
            self._radio = None
        logger.info("Scanner force shutdown complete")

    def get_scan_count(self) -> int:
        """Get the total number of scan cycles completed.

        Returns:
            Scan count from shared SpectrumData, or 0 if not set.
        """
        if self._spectrum_data is not None:
            return self._spectrum_data.get_scan_count()
        return 0

    def get_observation(self, channel: int) -> Optional[Any]:
        """Get the latest observation for a specific channel.

        Args:
            channel: Channel number (0-125).

        Returns:
            ChannelObservation or None if no data available.
        """
        validate_channel(channel)
        if self._spectrum_data is not None:
            return self._spectrum_data.get_observation(channel)
        return None

    def get_all_observations(self) -> dict:
        """Get all current observations (thread-safe copies).

        Returns:
            Dictionary mapping channel numbers to ChannelObservation copies.
        """
        if self._spectrum_data is not None:
            return self._spectrum_data.get_all_observations()
        return {}

    def get_channels_in_range(self) -> list:
        """Get list of channels in the configured range.

        Returns:
            List of channel numbers in the configured range.
        """
        if self._spectrum_data is not None:
            return self._spectrum_data.get_channels_in_range()
        return list(range(CHANNEL_MIN, CHANNEL_MAX + 1))

    def get_backend_label(self) -> str:
        """Get a human-readable label for the current backend.

        Returns:
            "Hardware (nRF24L01+)" or "Simulation (deterministic model)"
        """
        backend = self.get_backend()
        if backend == "hardware":
            return "Hardware (nRF24L01+)"
        return "Simulation (deterministic model)"

    def get_status_summary(self) -> dict:
        """Get a status summary for display in the UI.

        Returns:
            Dictionary with running status, backend, scan count, and backend label.
        """
        with self._lock:
            return {
                "running": self._running,
                "backend": self._backend,
                "backend_label": self.get_backend_label(),
                "scan_count": self.get_scan_count(),
            }