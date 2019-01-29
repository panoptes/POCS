from threading import Event
from warnings import warn

from astropy import units as u

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
        # For SBIG cameras serial_number and port are synomymous but at least one must be set
        kwargs['serial_number'] = kwargs.get('serial_number', kwargs.get('port'))
        kwargs['port'] = kwargs.get('port', kwargs.get('serial_number'))
        kwargs['readout_time'] = 1.0
        kwargs['file_extension'] = 'fits'
        super().__init__(name, *args, **kwargs)
        self.connect()
        if filter_type is not None:
            # connect() will have set this based on camera info, but that doesn't know about filters
            # upstream of the CCD. Can be set manually here, or handled by a filterwheel attribute.
            self._filter_type = filter_type
        if self.is_connected:
            # Set and enable cooling, if a set point has been given.
            if set_point is not None:
                self.ccd_set_point = set_point
                self.ccd_cooling_enabled = True
            else:
                self.ccd_cooling_enabled = False
            self.logger.info('{} initialised'.format(self))

# Properties

    @AbstractCamera.uid.getter
    def uid(self):
        """Return unique identifier for camera.

        Need to overide this because the base class only returns the 1st
        6 characters of the serial number, which is not a unique identifier
        for most of the camera types
        """
        return self._serial_number

    @property
    def ccd_temp(self):
        """
        Current temperature of the camera's image sensor.
        """
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDTemperature * u.Celsius

    @property
    def ccd_set_point(self):
        """
        Current value of the CCD set point, the target temperature for the camera's
        image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity.
        """
        return self._SBIGDriver.query_temp_status(self._handle).ccdSetpoint * u.Celsius

    @ccd_set_point.setter
    def ccd_set_point(self, set_point):
        self.logger.debug("Setting {} cooling set point to {}".format(self.name, set_point))
        enabled = self.ccd_cooling_enabled
        self._SBIGDriver.set_temp_regulation(self._handle, set_point, enabled)

    @property
    def ccd_cooling_enabled(self):
        """
        Current status of the camera's image sensor cooling system (enabled/disabled).

        Can be set by assigning a bool.
        """
        return bool(self._SBIGDriver.query_temp_status(self._handle).coolingEnabled)

    @ccd_cooling_enabled.setter
    def ccd_cooling_enabled(self, enabled):
        self.logger.debug("Setting {} cooling enabled to {}".format(self.name, enabled))
        set_point = self.ccd_set_point
        self._SBIGDriver.set_temp_regulation(self._handle, set_point, enabled)

    @property
    def ccd_cooling_power(self):
        """
        Current power level of the camera's image sensor cooling system (as
        a percentage of the maximum).
        """
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDPower

# Methods

    def __str__(self):
        # For SBIG cameras uid and port are both aliases for serial number so
        # shouldn't include both
        s = "{} ({})".format(self.name, self.uid)

        if self.focuser:
            s += ' with {}'.format(self.focuser.name)
            if self.filterwheel:
                s += ' & {}'.format(self.filterwheel.name)
        elif self.filterwheel:
            s += ' with {}'.format(self.filterwheel.name)

        return s

    def connect(self):
        """
        Connect to SBIG camera.

        Gets a 'handle', serial number and specs/capabilities from the driver
        """
        self.logger.debug('Connecting to {} ({})'.format(self.name, self.port))

        # Claim handle from the SBIGDriver, store camera info.
        self._handle, self._info = self._SBIGDriver.assign_handle(serial=self.port)
        if self._handle == INVALID_HANDLE_VALUE:
            message = 'Could not connect to {} ({})!'.format(self.name, self.port)
            self.logger.error(message)
            warn(message)
            self._connected = False
            return

        self.logger.debug("{} connected".format(self.name))
        self._connected = True
        self._serial_number = self._info['serial number']
        self.model = self._info['camera name']

        if self._info['colour']:
            if self._info['Truesense']:
                self._filter_type = 'CRGB'
            else:
                self._filter_type = 'RGGB'
        else:
            self._filter_type = 'M'

        if self.filterwheel and not self.filterwheel.is_connected:
            # Need to defer connection of SBIG filter wheels until after camera is connected
            # so do it here.
            self.filterwheel.connect()

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
            blocking (bool, optional): If False (default) returns immediately after starting
                the exposure, if True will block until it completes.

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

        return header
