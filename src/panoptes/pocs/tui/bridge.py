"""In-process command bridge from the TUI to a running POCS instance."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from panoptes.utils.config.store import get_config, set_config


class Bridge:
    """Abstract the command channel between the TUI and POCS.

    In v1 this is always in-process: the TUI holds a direct reference to the
    POCS instance and calls its methods from a small thread pool so the render
    loop is never blocked.
    """

    def __init__(self, pocs: Any = None) -> None:
        """Initialize the bridge.

        Args:
            pocs: Optional in-process POCS instance.
        """
        self._pocs = pocs
        self._run_thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pocs-tui-bridge")

    @property
    def is_connected(self) -> bool:
        """Return whether the bridge has an attached POCS instance."""
        return self._pocs is not None

    @property
    def pocs_state(self) -> str:
        """Return the current POCS state string."""
        if self._pocs is None:
            return "offline"
        try:
            return str(self._pocs.state)
        except Exception:
            return "unknown"

    @property
    def run_active(self) -> bool:
        """Return whether the state-machine run thread appears active."""
        if self._pocs is None:
            return False
        return getattr(self._pocs, "do_states", False) and (
            self._run_thread is not None and self._run_thread.is_alive()
        )

    def connect(self, pocs: Any) -> None:
        """Attach a POCS instance to the bridge.

        Args:
            pocs: Running POCS instance.
        """
        self._pocs = pocs

    def initialize(self) -> None:
        """Initialize POCS hardware in a background thread."""
        if self._pocs is None:
            return
        self._executor.submit(self._pocs.initialize)

    def start_run(self) -> None:
        """Start the POCS state-machine run loop in a background thread."""
        if self._pocs is None or self.run_active:
            return
        self._run_thread = threading.Thread(target=self._pocs.run, name="pocs-run", daemon=True)
        self._run_thread.start()

    def stop_run(self) -> None:
        """Interrupt the POCS run loop."""
        if self._pocs is None:
            return
        self._executor.submit(self._pocs.stop_states)

    def park(self) -> None:
        """Request the mount to park."""
        if self._pocs is None:
            return

        def _do_park() -> None:
            try:
                self._pocs.next_state = "parking"
            except Exception:
                pass

        self._executor.submit(_do_park)

    def abort_exposure(self) -> None:
        """Abort all active camera exposures."""
        if self._pocs is None:
            return

        def _do_abort() -> None:
            try:
                obs = self._pocs.observatory
                if obs and obs.cameras:
                    for cam in obs.cameras.values():
                        if hasattr(cam, "is_exposing") and cam.is_exposing:
                            cam.stop_observing.set()
            except Exception:
                pass

        self._executor.submit(_do_abort)

    def power_down(self) -> None:
        """Run the full POCS power-down sequence."""
        if self._pocs is None:
            return
        self._executor.submit(self._pocs.power_down)

    def get_config(self, key: str | None = None, default: Any = None) -> Any:
        """Read a config value from the in-memory config store.

        Args:
            key: Optional dotted config key.
            default: Fallback value on failure.

        Returns:
            Config value or default.
        """
        try:
            return get_config(key, default=default)
        except Exception:
            return default

    def set_config(self, key: str, value: Any) -> bool:
        """Write a config value and persist to disk.

        Args:
            key: Dotted config key.
            value: New config value.

        Returns:
            True on success, else False.
        """
        try:
            set_config(key, value, persist=True)
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        """Shut down the executor cleanly."""
        self._executor.shutdown(wait=False, cancel_futures=True)
