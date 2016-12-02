import subprocess

from astropy import units as u

from ..utils import error

from .camera import AbstractCamera

from .sbigudrv import SBIGDriver


class Camera(AbstractCamera):

    # Class variable to store reference to the one and only one instance of SBIGDriver
    _SBIGDriver = None

    def __new__(cls, *args, **kwargs):
        if Camera._SBIGDriver == None:
            # Creating a camera but there's no SBIGDriver instance yet. Create one.
            Camera._SBIGDriver = SBIGDriver(*args, **kwargs)
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.debug("Connecting SBIG camera")
        self.connect()
        self.logger.debug("{} connected".format(self.name))

    def connect(self):
        self.logger.debug('Connecting to camera')

        # Claim next unassigned handle from the SBIGDriver, store basic camera info.
        self._handle, self._camera_type, self._name, self._serial_number = self._SBIGDriver.assign_handle()

        self._connected = True

    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """ Take an exposure for given number of seconds """
        raise NotImplementedError()

    @property
    def CCD_temp(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDTemperature

    @property
    def CCD_set_point(self):
        return self._SBIGDriver.query_temp_status(self._handle).ccdSetpoint

    @CCD_set_point.setter
    def CCD_set_point(self, set_point):
        self._SBIGDriver.set_temp_regulation(self._handle, set_point)
                          
    @property
    def CCD_cooling_enabled(self):
        return bool(self._SBIGDriver.query_temp_status(self._handle).coolingEnabled)

    @property
    def CCD_cooling_power(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDPower
