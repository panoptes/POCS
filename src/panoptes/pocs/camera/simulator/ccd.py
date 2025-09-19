"""Simulated cooled CCD camera using the SDK camera interfaces.

Provides a minimal SDKDriver shim (loading libc) and a Camera implementation
that simulates cooling behavior (temperature, cooling power) and connects like
an SDK-backed device for use in tests and simulations.
"""
import math
import random
import time
from abc import ABC

from contextlib import suppress
import astropy.units as u

from panoptes.pocs.camera.simulator.dslr import Camera as SimCamera
from panoptes.pocs.camera.sdk import AbstractSDKDriver, AbstractSDKCamera
from panoptes.utils.config.client import get_config


class SDKDriver(AbstractSDKDriver):
    """Lightweight simulated SDK driver used for the simulator camera."""
    def __init__(self, library_path=None, **kwargs):
        # Get library loader to load libc, which should usually be present...
        super().__init__(name="c", library_path=library_path, **kwargs)

    def get_SDK_version(self):
        """Return a human-readable version string for the simulated SDK."""
        return "Simulated SDK Driver v0.001"

    def get_devices(self):
        """Return simulated device mapping from the main configuration.

        Returns:
            dict: Mapping of simulated camera names to their ports/IDs as
                configured under 'cameras.devices'.
        """
        self.logger.debug(f"Getting camera device connection config for {self}")
        camera_devices = dict()
        for cam_info in get_config("cameras.devices"):
            name = cam_info.get("name") or cam_info.get("model")
            port = cam_info.get("port") or cam_info.get("serial_number")
            camera_devices[name] = port

        self.logger.trace(f"camera_devices={camera_devices!r}")

        return camera_devices


class Camera(AbstractSDKCamera, SimCamera, ABC):
    """Simulated cooled camera that follows the AbstractSDKCamera contract.

    Combines the DSLR simulator behavior with SDK-style cooling controls to
    emulate a cooled scientific camera for testing pipeline behavior.
    """
    def __init__(
        self,
        name="Simulated SDK camera",
        driver=SDKDriver,
        target_temperature=0 * u.Celsius,
        *args,
        **kwargs,
    ):
        kwargs.update({"target_temperature": target_temperature})
        super().__init__(name, driver, *args, **kwargs)

    @AbstractSDKCamera.cooling_enabled.getter
    def cooling_enabled(self):
        """Whether simulated cooling is currently enabled.

        Returns:
            bool: True if cooling is enabled.
        """
        return self._cooling_enabled

    @AbstractSDKCamera.target_temperature.getter
    def target_temperature(self):
        """Simulated target temperature for the sensor.

        Returns:
            astropy.units.Quantity: Target temperature in degrees Celsius.
        """
        return self._target_temperature

    @property
    def temperature(self):
        """Current simulated sensor temperature.

        The temperature drifts exponentially toward a limit set by cooling state
        with a small random jitter added.

        Returns:
            astropy.units.Quantity: Simulated temperature in degrees Celsius.
        """
        now = time.monotonic()
        delta_time = (now - self._last_time) / self._time_constant

        if self.cooling_enabled:
            limit_temp = max(self.target_temperature, self._min_temp)
        else:
            limit_temp = self._max_temp

        delta_temp = limit_temp - self._last_temp
        temperature = limit_temp - delta_temp * math.exp(-delta_time)
        add_temp = random.uniform(-self._temp_var / 2, self._temp_var / 2)
        temperature += random.uniform(-self._temp_var / 2, self._temp_var / 2)
        self.logger.trace(f"Temp adding {add_temp:.02f} \t Total: {temperature:.02f} for {self}")

        return temperature

    @property
    def cooling_power(self):
        """Simulated cooling power level.

        Returns:
            astropy.units.Quantity: Cooling duty cycle as a percentage.
        """
        if self.cooling_enabled:
            return (
                100.0
                * float((self._max_temp - self.temperature) / (self._max_temp - self._min_temp))
                * u.percent
            )
        else:
            return 0.0 * u.percent

    def connect(self):
        """Initialize the simulated camera and cooling parameters."""
        self._is_cooled_camera = True
        self._cooling_enabled = False
        self._temperature = 5 * u.Celsius
        self._max_temp = 25 * u.Celsius
        self._min_temp = -15 * u.Celsius
        self._temp_var = 0.05 * u.Celsius
        self._time_constant = 0.25
        self._last_temp = 25 * u.Celsius
        self._last_time = time.monotonic()
        self._connected = True

    def _set_target_temperature(self, target):
        """Set the simulated target temperature.

        Args:
            target (astropy.units.Quantity | float): Desired sensor setpoint in C.
        """
        # Upon init the camera won't have an existing temperature.
        with suppress(AttributeError):
            self._last_temp = self.temperature
        self._last_time = time.monotonic()
        if not isinstance(target, u.Quantity):
            target = target * u.Celsius
        self._target_temperature = target.to(u.Celsius)

    def _set_cooling_enabled(self, enable):
        """Enable or disable simulated cooling.

        Args:
            enable (bool): True to enable, False to disable.
        """
        self._last_temp = self.temperature
        self._last_time = time.monotonic()
        self._cooling_enabled = bool(enable)
