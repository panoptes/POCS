import httpx
from astropy.coordinates import SkyCoord
from panoptes.utils.serializers import from_json

from panoptes.pocs.mount.mount import AbstractMount


class Mount(AbstractMount):
    """A proxy Mount class that delegates commands to a remote FastAPI service."""

    def __init__(self, location, endpoint_url="http://localhost:8001", *args, **kwargs):
        # We don't necessarily need the commands dict here since the real mount
        # on the remote end has it, but AbstractMount requires commands in its
        # _setup_commands. Let's let the parent initialize.
        # We might need to mock commands or just pass an empty dict.
        kwargs.setdefault("commands", {})
        super().__init__(location, *args, **kwargs)
        self.endpoint_url = endpoint_url
        self.client = httpx.Client(timeout=300.0)  # Long timeout for blocking slews
        self.logger.info(f"Initialized RemoteMount pointing to {self.endpoint_url}")

    def _get(self, path):
        try:
            response = self.client.get(f"{self.endpoint_url}/{path}")
            response.raise_for_status()
            data = from_json(response.text)
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return data
        except Exception as e:
            self.logger.error(f"Remote mount GET {path} failed: {e}")
            return None

    def _post(self, path, json=None, params=None):
        try:
            response = self.client.post(f"{self.endpoint_url}/{path}", json=json, params=params)
            response.raise_for_status()
            data = from_json(response.text)
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return data.get("result", True) if isinstance(data, dict) else data
        except Exception as e:
            self.logger.error(f"Remote mount POST {path} failed: {e}")
            return None

    def connect(self):
        self._is_connected = self._post("connect")
        return self._is_connected

    def initialize(self, *args, **kwargs):
        self._is_initialized = self._post("initialize")
        return self._is_initialized

    def disconnect(self):
        self._post("disconnect")
        self._is_connected = False

    @property
    def is_connected(self):
        self._is_connected = self._get("is_connected")
        return self._is_connected

    @property
    def is_initialized(self):
        self._is_initialized = self._get("is_initialized")
        return self._is_initialized

    @property
    def is_parked(self):
        self._is_parked = self._get("is_parked")
        return self._is_parked

    @property
    def is_home(self):
        self._is_home = self._get("is_home")
        return self._is_home

    @property
    def is_tracking(self):
        self._is_tracking = self._get("is_tracking")
        return self._is_tracking

    @property
    def is_slewing(self):
        self._is_slewing = self._get("is_slewing")
        return self._is_slewing

    @property
    def state(self):
        self._state = self._get("state")
        return self._state

    @property
    def has_target(self):
        return self._get("has_target")

    @property
    def status(self):
        try:
            response = self.client.get(f"{self.endpoint_url}/status")
            response.raise_for_status()
            data = from_json(response.text)
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return data
        except Exception as e:
            self.logger.error(f"Remote mount GET status failed: {e}")
            return {}

    def get_target_coordinates(self):
        coords_str = self._get("get_target_coordinates")
        if coords_str:
            return SkyCoord(coords_str)
        return None

    def set_target_coordinates(self, coords):
        if coords is None:
            return False
        return self._post("set_target_coordinates", json={"coords": coords.to_string("hmsdms")})

    def get_current_coordinates(self):
        coords_str = self._get("get_current_coordinates")
        if coords_str:
            return SkyCoord(coords_str)
        return None

    def slew_to_target(self, blocking=False, timeout=180.0):
        return self._post("slew_to_target", params={"blocking": blocking, "timeout": timeout})

    def slew_to_coordinates(self, coords, *args, **kwargs):
        return self._post("slew_to_coordinates", json={"coords": coords.to_string("hmsdms")})

    def slew_to_home(self, blocking=False, timeout=180.0):
        return self._post("slew_to_home", params={"blocking": blocking, "timeout": timeout})

    def search_for_home(self):
        return self._post("search_for_home")

    def park(self, *args, **kwargs):
        return self._post("park")

    def unpark(self):
        return self._post("unpark")

    def set_tracking_rate(self, direction="ra", delta=1.0):
        return self._post("set_tracking_rate", params={"direction": direction, "delta": delta})
