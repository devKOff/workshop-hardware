"""Custom exceptions for RF Spectrum Visualizer."""


class RFVisualizerError(Exception):
    """Base exception for RF Visualizer errors."""
    pass


class HardwareError(RFVisualizerError):
    """Raised when hardware operations fail."""
    pass


class RadioInitializationError(HardwareError):
    """Raised when radio initialization fails."""
    pass


class SPIError(HardwareError):
    """Raised when SPI communication fails."""
    pass


class RadioNotFoundError(HardwareError):
    """Raised when radio hardware is not detected."""
    pass


class ChannelError(RFVisualizerError):
    """Raised for invalid channel operations."""
    pass


class InvalidChannelError(ChannelError):
    """Raised when channel number is out of range."""
    pass


class ConfigurationError(RFVisualizerError):
    """Raised for invalid configuration."""
    pass


class ScannerError(RFVisualizerError):
    """Raised for scanner thread errors."""
    pass


class ScannerNotRunningError(ScannerError):
    """Raised when scanner operation requires running scanner."""
    pass


class ScannerAlreadyRunningError(ScannerError):
    """Raised when attempting to start an already running scanner."""
    pass


class ExportError(RFVisualizerError):
    """Raised when export operations fail."""
    pass


class MitigationError(RFVisualizerError):
    """Raised for mitigation subsystem errors."""
    pass


class InsufficientDataError(RFVisualizerError):
    """Raised when insufficient samples for calculation."""
    pass


class BackendError(RFVisualizerError):
    """Raised for backend-related errors."""
    pass


class SimulationError(BackendError):
    """Raised for simulation backend errors."""
    pass