"""Storage module for RF Spectrum Visualizer V3.

Provides shared storage services for spectrum data, blocklist, and
application state across all three GUI tools (Live Spectrum, Start
Analysis, Blocker).

Key components:
- SpectrumData wrapper: thread-safe storage for channel observations,
  with backend tracking and export capabilities.
- Persistence: blocklist JSON file management shared across restarts.
"""

from ..services.scanner import ScannerService
from ..services.blocklist import BlocklistService
from ..services.analysis import AnalysisService