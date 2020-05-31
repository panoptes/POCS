import math
import random
import time
from abc import ABC

from contextlib import suppress
import astropy.units as u

from panoptes.pocs.camera.simulator import Camera
from panoptes.pocs.camera.sdk import AbstractSDKDriver, AbstractSDKCamera


class SDKDriver(AbstractSDKDriver):
    def __init__(self, library_path=None, **kwargs):
        # Get library loader to load libc, which should usually be present...
        super().__init__(name='c', library_path=library_path, **kwargs)

    def get_SDK_version(self):
        return "Simulated SDK Driver v0.001"

    def get_devices(self):
        cameras = {'SSC007': 'DEV_USB0',
                   'SSC101': 'DEV_USB1',
                   'SSC999': 'DEV_USB2'}
        return cameras


class Camera(AbstractSDKCamera, Camera, ABC):
    def __init__(self,
                 name='Simulated SDK camera',
                 driver=SDKDriver,
                 target_temperature=0 * u.Celsius,
                 *args, **kwargs):
        kwargs.update({'target_temperature': target_temperature})
        super().__init__(name, driver, *args, **kwargs)

    @property
    def cooling_enabled(self):
        return self._cooling_enabled

    @cooling_enabled.setter
    def cooling_enabled(self, enable):
        self._last_temp = self.temperature
        self._last_time = time.monotonic()
        self._cooling_enabled = bool(enable)

    @property
    def target_temperature(self):
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, target):
        # Upon init the camera won't have an existing temperature.
        with suppress(AttributeError):
            self._last_temp = self.temperature
        self._last_time = time.monotonic()
        if not isinstance(target, u.Quantity):
            target = target * u.Celsius
        self._target_temperature = target.to(u.Celsius)

    @property
    def temperature(self):
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
        self.logger.trace(f"Temp adding {add_temp:.02f} \t Total: {temperature:.02f}")

        return temperature

    @property
    def cooling_power(self):
        if self.cooling_enabled:
            return 100.0 * float((self._max_temp - self.temperature) /
                                 (self._max_temp - self._min_temp))
        else:
            return 0.0

    def connect(self):
        self._is_cooled_camera = True
        self._cooling_enabled = False
        self._temperature = 25 * u.Celsius
        self._max_temp = 25 * u.Celsius
        self._min_temp = -15 * u.Celsius
        self._temp_var = 0.05 * u.Celsius
        self._time_constant = 0.25
        self._last_temp = 25 * u.Celsius
        self._last_time = time.monotonic()
        self._connected = True
