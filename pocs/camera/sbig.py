import subprocess

from astropy import units as u

from ..utils import error

from .camera import AbstractCamera

from .sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE


class Camera(AbstractCamera):

    # Class variable to store reference to the one and only one instance of SBIGDriver
    _SBIGDriver = None

    def __new__(cls, *args, **kwargs):
        if Camera._SBIGDriver == None:
            # Creating a camera but there's no SBIGDriver instance yet. Create one.
            Camera._SBIGDriver = SBIGDriver(*args, **kwargs)
        return super().__new__(cls)

    def __init__(self, *args, serial_number=None, set_point=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.debug("Connecting SBIG camera")
        self.connect(serial_number, set_point)
        self.logger.debug("{} connected".format(self.name))

    def connect(self, serial_number=None, set_point=None):
        self.logger.debug('Connecting to camera')

        # Claim next unassigned handle from the SBIGDriver, store basic camera info.
        self._handle, self._camera_type, self._name, self._serial_number = self._SBIGDriver.assign_handle(serial_number=serial_number)

        if self._handle != INVALID_HANDLE_VALUE:
            self._connected = True
        
        # If given a CCD temperature set point enable cooling.
        if set_point and self._connected:
            self.logger.debug("Setting {} cooling set point to {}",format(self.name, set_point)
            self._DBIGDriver.set_temp_regulation(self.handle)


    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """ Take an exposure for given number of seconds """
        raise NotImplementedError()

    @property
    def uid(self):
        # Unlike Canon DSLRs 1st 6 characters of serial number is *not* a unique identifier.
        # Need to use the whole thing.
        return self._serial_number
    
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
