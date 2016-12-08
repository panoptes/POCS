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

    def __init__(self, set_point=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.debug("Connecting SBIG camera")
        self.connect(set_point)
        self.logger.debug("{} connected".format(self.name))

# Properties
        
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

# Methods
    
    def __str__(self):
        # uid and port are both aliases for serial number so shouldn't include both
        return "{}({})".format(self.name, self.uid)

    def connect(self, set_point=None):
        self.logger.debug('Connecting to camera {}'.format(self.uid))

        # Claim handle from the SBIGDriver, store camera info.
        self._handle, self._info = self._SBIGDriver.assign_handle(serial=self.port)

        if self._handle != INVALID_HANDLE_VALUE:
            self._connected = True
            self._serial_number = self._info['serial_number']
        
            # If given a CCD temperature set point enable cooling.
            if set_point and self._connected:
                self.logger.debug("Setting {} cooling set point to {}",format(self.name, set_point))
                self._DBIGDriver.set_temp_regulation(self.handle, set_point)

        else:
            self.logger.warning('Could not connect to camera {}!'.format(self.uid))

    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """ Take an exposure for given number of seconds """
        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        return self._SBIGDriver.take_exposure(handle, seconds, filename)                             

