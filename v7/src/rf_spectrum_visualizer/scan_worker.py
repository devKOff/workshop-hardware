"""rf_spectrum_visualizer.scan_worker

Background scan worker that runs a ScanBackend in a worker thread and
publishes results through a queue.  The GUI thread pulls from the queue
and updates the Live Spectrum page.

Hardware imports (pyrf24) happen only inside HardwareBackend methods, never
at module import time, so this module is safe to import on any machine.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Optional

from rf_spectrum_visualizer.scan_backend import (
    ChannelStats,
    HardwareBackend,
    ScanBackend,
    SimBackend,
)


@dataclass
class ScanResult:
    """A single channel scan result published to the GUI queue."""

    stats: ChannelStats


@dataclass
class ScanProgress:
    """Progress message published to the GUI queue."""

    channel: int
    total: int
    message: str


@dataclass
class ScanError:
    """Error message published to the GUI queue."""

    message: str


@dataclass
class ScanComplete:
    """Completion signal published to the GUI queue."""

    pass


class ScanWorker:
    """Runs channel scans in a background thread.

    The GUI thread calls start() and polls result_queue.get() (non-blocking)
    via tkinter.after().  The worker thread owns the ScanBackend lifecycle
    (open / close) so the radio is never touched from the GUI thread.
    """

    def __init__(self, backend: Optional[ScanBackend] = None) -> None:
        self.backend = backend or SimBackend()
        self.result_queue: "queue.Queue[object]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._channels: list[int] = []
        self._samples: int = 100

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        channels: list[int],
        samples: int = 100,
        backend: Optional[ScanBackend] = None,
    ) -> None:
        """Begin scanning `channels` in a background thread.

        Safe to call only when not already running.
        """
        if self.running:
            return
        if backend is not None:
            self.backend = backend
        self._channels = list(channels)
        self._samples = samples
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Request the worker stop after the current channel finishes."""
        self._stop.set()

    def _run(self) -> None:
        """Worker thread entry point."""
        self.backend.open()
        try:
            total = len(self._channels)
            for idx, ch in enumerate(self._channels, start=1):
                if self._stop.is_set():
                    self.result_queue.put(
                        ScanError(message="Scan stopped by user.")
                    )
                    break
                self.result_queue.put(
                    ScanProgress(channel=ch, total=total, message=f"Scanning {ch} / {total}")
                )
                try:
                    stats = self.backend.scan_channel(ch, self._samples)
                except Exception as exc:  # hardware error on one channel
                    self.result_queue.put(
                        ScanError(message=f"Channel {ch}: {exc}")
                    )
                    continue
                self.result_queue.put(ScanResult(stats=stats))
            if not self._stop.is_set():
                self.result_queue.put(ScanComplete())
        finally:
            self.backend.close()
