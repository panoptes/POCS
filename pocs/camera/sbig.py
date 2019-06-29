from contextlib import suppress

from astropy import units as u

from pocs.camera.sdk import AbstractSDKCamera
from pocs.camera.sbigudrv import INVALID_HANDLE_VALUE
from pocs.camera.sbigudrv import SBIGDriver
from pocs.utils.images import fits as fits_utils
from pocs.utils import error


class Camera(AbstractSDKCamera):
    _driver = None
    _cameras = {}
    _assigned_cameras = set()

    def __init__(self,
                 name='SBIG Camera',
                 temperature_tolerance=0.5 * u.Celsius,
                 *args, **kwargs):
        super().__init__(name, SBIGDriver, *args, **kwargs)
        if not isinstance(temperature_tolerance, u.Quantity):
            temperature_tolerance = temperature_tolerance * u.Celsius
        self._temperature_tolerance = temperature_tolerance
        self.logger.info('{} initialised'.format(self))

    def __del__(self):
        with suppress(AttributeError):
            self._driver.set_handle(INVALID_HANDLE_VALUE)  # Shortcut to closing device & driver
            self.logger.debug("Closed SBIG camera device & driver")
        super().__del__()

# Properties

    @property
    def ccd_temp(self):
        """
        Current temperature of the camera's image sensor.
        """
        temp_status = self._driver.query_temp_status(self._handle)
        return temp_status['imaging_ccd_temperature']

    @property
    def ccd_set_point(self):
        """
        Current value of the CCD set point, the target temperature for the camera's
        image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity.
        """
        temp_status = self._driver.query_temp_status(self._handle)
        return temp_status['ccd_set_point']

    @ccd_set_point.setter
    def ccd_set_point(self, set_point):
        if not isinstance(set_point, u.Quantity):
            set_point = set_point * u.Celsius
        self.logger.debug("Setting {} cooling set point to {}".format(self, set_point))
        enabled = self.ccd_cooling_enabled
        self._driver.set_temp_regulation(self._handle, set_point, enabled)

    @property
    def ccd_cooling_enabled(self):
        """
        Current status of the camera's image sensor cooling system (enabled/disabled).

        Can be set by assigning a bool.
        """
        temp_status = self._driver.query_temp_status(self._handle)
        return temp_status['cooling_enabled']

    @ccd_cooling_enabled.setter
    def ccd_cooling_enabled(self, enable):
        self.logger.debug("Setting {} cooling enabled to {}".format(self.name, enable))
        set_point = self.ccd_set_point
        self._driver.set_temp_regulation(self._handle, set_point, enable)

    @property
    def ccd_cooling_power(self):
        """
        Current power level of the camera's image sensor cooling system (as
        a percentage of the maximum).
        """
        temp_status = self._driver.query_temp_status(self._handle)
        return temp_status['imaging_ccd_power']

    @property
    def is_exposing(self):
        """ True if an exposure is currently under way, otherwise False """
        return self._driver.get_exposure_status(self._handle) == 'CS_INTEGRATING'

# Methods

    def connect(self):
        """
        Connect to SBIG camera.

        Gets a 'handle', serial number and specs/capabilities from the driver
        """
        self.logger.debug('Connecting to {}'.format(self))
        # This will close device and driver, ensuring it is ready to access a new camera
        self._driver.set_handle(handle=INVALID_HANDLE_VALUE)
        self._driver.open_driver()
        self._driver.open_device(self._address)
        self._driver.establish_link()
        link_status = self._driver.get_link_status()
        if not link_status['established']:
            raise error.PanError("Could not establish link to {}.".format(self))
        self._handle = self._driver.get_driver_handle()
        if self._handle == INVALID_HANDLE_VALUE:
            raise error.PanError("Could not connect to {}.".format(self))

        self._info = self._driver.get_ccd_info(self._handle)
        self.model = self.properties['camera name']
        if self.properties['colour']:
            if self.properties['Truesense']:
                self._filter_type = 'CRGB'
            else:
                self._filter_type = 'RGGB'
        else:
            self._filter_type = 'M'

        # Stop camera from skipping lowering of Vdd for exposures of 3 seconds of less
        self._driver.disable_vdd_optimized(self._handle)

        self._connected = True

        if self.filterwheel and not self.filterwheel.is_connected:
            # Need to defer connection of SBIG filter wheels until after camera is connected
            # so do it here.
            self.filterwheel.connect()

# Private methods

    def _start_exposure(self, seconds, filename, dark, header, *args, **kwargs):
        # Check temerature is OK.
        if self.ccd_cooling_enabled:
            t_error = abs(self.ccd_temp - self.ccd_set_point)
            if t_error > self._temperature_tolerance or self.ccd_cooling_power == 100 * u.percent:
                self.logger.warning('Unstable CCD temperature in {}'.format(self))

        readout_mode = 'RM_1X1'  # Unbinned mode
        top = 0  # Unwindowed too
        left = 0
        height = self.properties['readout modes'][readout_mode]['height']
        width = self.properties['readout modes'][readout_mode]['width']

        self._driver.start_exposure(handle=self._handle,
                                    seconds=seconds,
                                    dark=dark,
                                    antiblooming=self.properties['imaging ABG'],
                                    readout_mode=readout_mode,
                                    top=top,
                                    left=left,
                                    height=height,
                                    width=width)
        readout_args = (filename,
                        readout_mode,
                        top,
                        left,
                        height,
                        width,
                        header)
        return readout_args

    def _readout(self, filename, readout_mode, top, left, height, width, header):
        exposure_status = Camera._driver.get_exposure_status(self._handle)
        if exposure_status == 'CS_INTEGRATION_COMPLETE':
            try:
                image_data = Camera._driver.readout(self._handle,
                                                    readout_mode,
                                                    top,
                                                    left,
                                                    height,
                                                    width)
            except RuntimeError as err:
                raise error.PanError('Readout error on {}, {}'.format(self, err))
            else:
                fits_utils.write_fits(image_data,
                                      header,
                                      filename,
                                      self.logger)
        elif exposure_status == 'CS_IDLE':
            raise error.PanError("Exposure missing on {}".format(self))
        else:
            raise error.PanError("Unexpected exposure status on {}: '{}'".format(
                self, exposure_status))

    def _create_fits_header(self, seconds, dark):
        header = super()._create_fits_header(seconds, dark)

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
