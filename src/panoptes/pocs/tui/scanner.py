"""Background scanner for producing stable POCSModel snapshots."""

from __future__ import annotations

from threading import Event, Lock, Thread
from time import perf_counter
from typing import TYPE_CHECKING, Any

from panoptes.pocs.tui.model import CameraModel, POCSModel

if TYPE_CHECKING:
    from panoptes.utils.telemetry.client import TelemetryClient


def _fmt_float(value: Any) -> str:
    """Format a numeric value to two decimal places.

    Args:
        value: Value to format.

    Returns:
        Formatted number or ``"--"`` if unavailable.
    """
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "--"


class Scanner:
    """Polls runtime state in a background thread and swaps complete snapshots."""

    def __init__(self, pocs: Any = None, interval_s: float = 0.5) -> None:
        self._pocs = pocs
        self._interval_s = interval_s
        self._lock = Lock()
        self._stop_event = Event()
        self._force_event = Event()
        self._thread: Thread | None = None
        self._front = POCSModel()
        self._back = POCSModel()
        self._scan_count = 0
        self._client: TelemetryClient | None = None
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
            except Exception as err:  # pragma: no cover - defensive scanner guard
                self.last_exception = err

    def _scan_direct(self) -> POCSModel:
        """Read state directly from an in-process POCS instance.

        Used when a ``pocs`` object was passed at construction time, avoiding
        the need for a running telemetry server.

        Returns:
            A freshly populated model snapshot.
        """
        model = POCSModel()
        try:
            status = self._pocs.status
        except Exception:
            return model

        model.system.state = str(status.get("state", "unknown"))
        model.system.next_state = str(status.get("next_state", ""))
        model.system.run_active = bool(getattr(self._pocs, "do_states", False))

        obs_data = status.get("observatory", {})
        if obs_data:
            model.system.connected = bool(obs_data.get("can_observe", False))

            # Mount — boolean state from live properties; coordinates from status dict.
            obs_obj = getattr(self._pocs, "observatory", None)
            mount = getattr(obs_obj, "mount", None) if obs_obj else None
            if mount is not None:
                model.mount.connected = bool(getattr(mount, "is_initialized", False))
                model.mount.is_parked = bool(getattr(mount, "is_parked", True))
                model.mount.is_tracking = bool(getattr(mount, "is_tracking", False))
                model.mount.is_slewing = bool(getattr(mount, "is_slewing", False))
                mount_data = obs_data.get("mount", {})
                model.mount.ha = _fmt_float(mount_data.get("current_ha"))
                ra = mount_data.get("current_ra")
                dec = mount_data.get("current_dec")
                model.mount.ra = _fmt_float(ra) if ra is not None else "--"
                model.mount.dec = _fmt_float(dec) if dec is not None else "--"
                alt = mount_data.get("alt")
                az = mount_data.get("az")
                model.mount.alt = _fmt_float(alt) if alt is not None else "--"
                model.mount.az = _fmt_float(az) if az is not None else "--"

            # Cameras — read directly from observatory object.
            cameras = getattr(obs_obj, "cameras", {}) or {}
            for cam_name, cam in cameras.items():
                cam_model = CameraModel(name=cam_name)
                cam_model.connected = bool(getattr(cam, "is_connected", False))
                cam_model.is_exposing = bool(getattr(cam, "is_exposing", False))
                cam_model.temperature = _fmt_float(getattr(cam, "temperature", None))
                filter_name = getattr(cam, "filter_name", None)
                cam_model.filter_name = str(filter_name) if filter_name else "--"
                model.cameras.append(cam_model)

            # Current observation — under "observation" key in direct status.
            obs_status = obs_data.get("observation", {})
            if obs_status:
                field_name = str(obs_status.get("field_name", ""))
                model.scheduler.selected_field = field_name
                model.scheduler.observing.field_name = field_name
                model.scheduler.observing.exposure_s = float(obs_status.get("exptime", 0) or 0)
                model.scheduler.observing.current_exp_num = int(obs_status.get("current_exp", 0) or 0)

        return model

    def _scan(self) -> POCSModel:
        """Query telemetry and populate a fresh model snapshot.

        Returns:
            A newly populated model snapshot.
        """
        # Prefer direct in-process access when POCS is available.
        if self._pocs is not None:
            return self._scan_direct()

        if self._client is None:
            try:
                from panoptes.utils.telemetry.client import TelemetryClient

                self._client = TelemetryClient()
            except Exception:
                return POCSModel()

        model = POCSModel()

        try:
            events = self._client.current()
        except Exception:
            return model

        status_event = events.get("status")
        if status_event:
            data = status_event.data or {}
            model.system.state = str(data.get("state", "unknown"))
            model.system.next_state = str(data.get("next_state", ""))
            model.system.run_active = bool(data.get("run_active", False) or data.get("do_states", False))
            obs = data.get("observatory", {})
            model.system.connected = bool(obs.get("can_observe", False))

            mount_data = obs.get("mount", {})
            if mount_data:
                model.mount.connected = True
                model.mount.is_parked = bool(mount_data.get("is_parked", True))
                model.mount.is_tracking = bool(mount_data.get("is_tracking", False))
                model.mount.is_slewing = bool(mount_data.get("is_slewing", False))
                model.mount.ra = str(mount_data.get("ra", "--"))
                model.mount.dec = str(mount_data.get("dec", "--"))
                model.mount.ha = _fmt_float(mount_data.get("current_ha"))
                model.mount.alt = _fmt_float(mount_data.get("alt"))
                model.mount.az = _fmt_float(mount_data.get("az"))

            cameras_data = obs.get("cameras", {})
            items = cameras_data.items() if isinstance(cameras_data, dict) else []
            for cam_name, cam_info in items:
                cam = CameraModel(name=cam_name)
                cam.connected = True
                cam.is_exposing = bool(cam_info.get("is_exposing", False))
                cam.temperature = _fmt_float(cam_info.get("temperature"))
                cam.filter_name = str(cam_info.get("filter_name") or "--")
                model.cameras.append(cam)

            current_obs = obs.get("current_observation", {})
            if current_obs:
                field_name = str(current_obs.get("field_name", ""))
                model.scheduler.selected_field = field_name
                model.scheduler.observing.field_name = field_name
                model.scheduler.observing.exposure_s = float(current_obs.get("exp_time", 0) or 0)
                model.scheduler.observing.current_exp_num = int(current_obs.get("current_exp", 0) or 0)

        weather_event = events.get("weather")
        if weather_event:
            weather_data = weather_event.data or {}
            model.safety.good_weather = bool(weather_data.get("safe", False))
            model.safety.is_dark = bool(weather_data.get("is_dark", model.safety.is_dark))

        power_event = events.get("power")
        if power_event:
            power_data = power_event.data or {}
            model.safety.ac_power = bool(power_data.get("main", False))

        state_event = events.get("state")
        if state_event:
            state_data = state_event.data or {}
            model.system.state = str(state_data.get("dest", model.system.state))
            model.system.run_active = bool(state_data.get("do_states", model.system.run_active))
            model.safety.is_dark = bool(state_data.get("is_dark", model.safety.is_dark))

        return model
