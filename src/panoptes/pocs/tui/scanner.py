"""Background scanner for producing stable POCSModel snapshots."""

from __future__ import annotations

from threading import Event, Lock, Thread
from time import perf_counter
from typing import Any

from panoptes.pocs.tui.model import POCSModel


class Scanner:
    """Polls runtime state in a background thread and swaps complete snapshots."""

    def __init__(self, pocs: Any = None, interval_s: float = 0.5):
        self._pocs = pocs
        self._interval_s = interval_s
        self._lock = Lock()
        self._stop_event = Event()
        self._force_event = Event()
        self._thread: Thread | None = None
        self._front = POCSModel()
        self._back = POCSModel()
        self._scan_count = 0
        self.last_exception: Exception | None = None

    def start(self) -> None:
        """Start the scanner thread if it is not already running."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="pocs-tui-scanner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the scanner thread to stop and wait for it to exit."""
        self._stop_event.set()
        self._force_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(self._interval_s * 2, 0.1))

    def force_update(self) -> None:
        """Wake the scanner loop so it runs a scan immediately."""
        self._force_event.set()

    def snapshot(self) -> POCSModel:
        """Return the latest complete snapshot from the front buffer."""
        with self._lock:
            return self._front

    def _run(self) -> None:
        """Run scan loop with timeout polling and force-wake support."""
        while not self._stop_event.is_set():
            self._force_event.wait(timeout=self._interval_s)
            self._force_event.clear()

            start = perf_counter()
            try:
                scanned = self._scan()
                scanned.scan_time_ms = (perf_counter() - start) * 1000.0
                self._scan_count += 1
                scanned.scan_count = self._scan_count
                with self._lock:
                    self._back = self._front
                    self._front = scanned
            except Exception as err:  # pragma: no cover - defensive skeleton behavior
                self.last_exception = err

    def _scan(self) -> POCSModel:
        """Build and return a new POCS model snapshot.

        TODO: Query running POCS components and populate all model fields.
        """
        return POCSModel()
