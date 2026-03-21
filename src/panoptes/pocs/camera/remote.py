import threading
from typing import Any
from urllib.parse import quote

import httpx
from panoptes.utils import error
from panoptes.utils.serializers import from_json

from panoptes.pocs.camera.camera import AbstractCamera


class Camera(AbstractCamera):
    """A proxy Camera class that delegates commands to a remote FastAPI service."""

    def __init__(
        self,
        name="Remote Camera",
        model="remote",
        port=None,
        primary=False,
        endpoint_url="http://localhost:8002",
        *args,
        **kwargs,
    ):
        super().__init__(name=name, model=model, port=port, primary=primary, *args, **kwargs)
        self.endpoint_url = endpoint_url
        self.client = httpx.Client(timeout=300.0)
        # URL-safe camera name for routing
        self.safe_name = quote(self.name)
        self.logger.info(f"Initialized RemoteCamera {name} pointing to {self.endpoint_url}")

    def _get(self, path):
        try:
            response = self.client.get(f"{self.endpoint_url}/{self.safe_name}/{path}")
            response.raise_for_status()
            data = from_json(response.text)
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return data
        except Exception as e:
            self.logger.error(f"Remote camera GET {path} failed: {e}")
            return None

    def _post(self, path, json=None, params=None):
        try:
            response = self.client.post(
                f"{self.endpoint_url}/{self.safe_name}/{path}", json=json, params=params
            )
            response.raise_for_status()
            data = from_json(response.text)
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return data.get("result", True) if isinstance(data, dict) else data
        except Exception as e:
            self.logger.error(f"Remote camera POST {path} failed: {e}")
            return None

    def connect(self):
        self._connected = self._post("connect")
        return self._connected

    @property
    def is_connected(self):
        status = self._get("status")
        return status.get("is_connected", False) if status else False

    @property
    def temperature(self):
        status = self._get("status")
        return status.get("temperature") if status else None

    @property
    def target_temperature(self):
        status = self._get("status")
        return status.get("target_temperature") if status else None

    @target_temperature.setter
    def target_temperature(self, target):
        self._post("set_target_temperature", params={"target": target})

    @property
    def cooling_enabled(self):
        status = self._get("status")
        return status.get("cooling_enabled", False) if status else False

    @cooling_enabled.setter
    def cooling_enabled(self, enabled):
        self._post("set_cooling_enabled", params={"enabled": enabled})

    @property
    def cooling_power(self):
        status = self._get("status")
        return status.get("cooling_power", 0.0) if status else 0.0

    @property
    def is_exposing(self):
        status = self._get("status")
        return status.get("is_exposing", False) if status else False

    @property
    def is_ready(self):
        status = self._get("status")
        return status.get("is_ready", False) if status else False

    def take_exposure(
        self,
        seconds=1.0,
        filename=None,
        metadata=None,
        dark=False,
        blocking=False,
        timeout=10.0,
        *args,
        **kwargs,
    ):
        """Proxy exposure logic to remote node."""
        if not filename:
            raise error.PanError("Must pass filename for take_exposure")

        seconds_val = seconds.value if hasattr(seconds, "value") else seconds
        timeout_val = timeout.value if hasattr(timeout, "value") else timeout

        params = {
            "seconds": seconds_val,
            "filename": str(filename),
            "metadata": metadata or {},
            "dark": dark,
            "blocking": blocking,
            "timeout": timeout_val,
        }

        self._post("take_exposure", json=params)

        # The remote handles its own threading. We can just return a dummy thread
        # if blocking is false, since AbstractCamera expects a thread.
        dummy_thread = threading.Thread(target=lambda: None)
        dummy_thread.start()
        return dummy_thread

    def process_exposure(self, metadata, **kwargs):
        """Proxy processing logic to remote node."""
        self._post("process_exposure", json={"metadata": metadata})

    def _set_target_temperature(self, target):
        pass

    def _set_cooling_enabled(self, enable):
        pass

    def _start_exposure(self, seconds=None, filename=None, dark=False, header=None, *args, **kwargs):
        pass

    def _readout(self, *args, **kwargs):
        pass

    def _process_fits(self, file_path, metadata):
        return file_path
