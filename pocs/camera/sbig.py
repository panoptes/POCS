from threading import Event

from astropy import units as u
from astropy.io import fits

from pocs.camera import AbstractCamera
from pocs.camera.sbigudrv import INVALID_HANDLE_VALUE
from pocs.camera.sbigudrv import SBIGDriver

class Camera(AbstractCamera):

    # Class variable to store reference to the one and only one instance of SBIGDriver
    _SBIGDriver = None

    def __new__(cls, *args, **kwargs):
        if Camera._SBIGDriver is None:
            # Creating a camera but there's no SBIGDriver instance yet. Create one.
            Camera._SBIGDriver = SBIGDriver(*args, **kwargs)
        return super().__new__(cls)

    def __init__(self,
                 name='SBIG Camera',
                 set_point=None,
                 filter_type=None,
                 *args, **kwargs):
        kwargs['readout_time'] = 1.0
        kwargs['file_extension'] = 'fits'
        super().__init__(name, *args, **kwargs)
        self.connect()
        if filter_type is not None:
            # connect() will set this based on camera info, but that doesn't know about filters
            # upstream of the CCD.
            self.filter_type = filter_type
        # Set cooling (if set_point=None this will turn off cooling)
        if self.is_connected:
            self.CCD_set_point = set_point
            self.logger.info('\t\t\t {} initialised'.format(self))

# Properties

    @AbstractCamera.uid.getter
    def uid(self):
        # Unlike Canon DSLRs 1st 6 characters of serial number is *not* a unique identifier.
        # Need to use the whole thing.
        return self._serial_number

    @property
    def CCD_temp(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDTemperature * u.Celsius

    @property
    def CCD_set_point(self):
        return self._SBIGDriver.query_temp_status(self._handle).ccdSetpoint * u.Celsius

    @CCD_set_point.setter
    def CCD_set_point(self, set_point):
        self.logger.debug("Setting {} cooling set point to {}".format(self.name, set_point))
        self._SBIGDriver.set_temp_regulation(self._handle, set_point)

    @property
    def CCD_cooling_enabled(self):
        return bool(self._SBIGDriver.query_temp_status(self._handle).coolingEnabled)

    @property
    def CCD_cooling_power(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDPower

# Methods

    def __str__(self):
        # For SBIG cameras uid and port are both aliases for serial number so
        # shouldn't include both
        try:
            return "{} ({}) with {} focuser".format(self.name, self.uid, self.focuser.name)
        except AttributeError:
            return "{} ({})".format(self.name, self.uid)

    def connect(self):
        """
        Connect to SBIG camera.

        Gets a 'handle', serial number and specs/capabilities from the driver
        """
        self.logger.debug('Connecting to camera {}'.format(self.uid))

        # Claim handle from the SBIGDriver, store camera info.
        self._handle, self._info = self._SBIGDriver.assign_handle(serial=self.port)

        if self._handle == INVALID_HANDLE_VALUE:
            self.logger.error('Could not connect to {}!'.format(self.name))
            self._connected = False
            return

        self.logger.debug("{} connected".format(self.name))
        self._connected = True
        self._serial_number = self._info['serial number']
        self.model = self._info['camera name']

        if self._info['colour']:
            if self._info['Truesense']:
                self.filter_type = 'CRGB'
            else:
                self.filter_type = 'RGGB'
        else:
            self.filter_type = 'M'

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      *args,
                      **kwargs
                      ):
        """
        Take an exposure for given number of seconds and saves to provided filename.

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
            dark (bool, optional): Exposure is a dark frame (don't open shutter), default False

        Returns:
            threading.Event: Event that will be set when exposure is complete

        """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        self.logger.debug('Taking {} second exposure on {}: {}'.format(
            seconds, self.name, filename))
        exposure_event = Event()
        header = self._fits_header(seconds, dark)
        self._SBIGDriver.take_exposure(self._handle, seconds, filename,
                                       exposure_event, dark, header)

        if blocking:
            exposure_event.wait()

        return exposure_event

# Private methods

    def _fits_header(self, seconds, dark):
        header = super()._fits_header(seconds, dark)

        # Unbinned. Need to chance if binning gets implemented.
        readout_mode = 'RM_1X1'

        header.set('CAM-FW', self._info['firmware version'], 'Camera firmware version')
        header.set('XPIXSZ', self._info['readout modes'][readout_mode]['pixel width'].value,
                   'Microns')
        header.set('YPIXSZ', self._info['readout modes'][readout_mode]['pixel height'].value,
                   'Microns')
        header.set('EGAIN', self._info['readout modes'][readout_mode]['gain'].value,
                   'Electrons/ADU')

        if self.focuser:
            header = self.focuser._fits_header(header)

        return header
