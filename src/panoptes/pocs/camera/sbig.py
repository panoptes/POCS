from contextlib import suppress

from astropy import units as u

from panoptes.pocs.camera.sdk import AbstractSDKCamera
from panoptes.pocs.camera.sbigudrv import INVALID_HANDLE_VALUE
from panoptes.pocs.camera.sbigudrv import SBIGDriver
from panoptes.utils.images import fits as fits_utils
from panoptes.utils import error


class Camera(AbstractSDKCamera):
    _driver = None
    _cameras = {}
    _assigned_cameras = set()

    def __init__(self,
                 name='SBIG Camera',
                 *args, **kwargs):
        super().__init__(name, SBIGDriver, *args, **kwargs)
        self.logger.info('{} initialised'.format(self))

    def __del__(self):
        with suppress(AttributeError):
            self._driver.set_handle(INVALID_HANDLE_VALUE)  # Shortcut to closing device & driver
            self.logger.debug("Closed SBIG camera device & driver")
        super().__del__()

# Properties

    @property
    def egain(self):
        """Image sensor gain in e-/ADU as reported by the camera."""
        return self.properties['readout modes']['RM_1X1']['gain']

    @property
    def temperature(self):
        """
        Current temperature of the camera's image sensor.
        """
        temp_status = self._driver.query_temp_status(self._handle)
        return temp_status['imaging_ccd_temperature']

    @property
    def target_temperature(self):
        """
        Current value of the target temperature for the camera's image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity.
        """
        temp_status = self._driver.query_temp_status(self._handle)
        return temp_status['ccd_set_point']

    @target_temperature.setter
    def target_temperature(self, target):
        if not isinstance(target, u.Quantity):
            target = target * u.Celsius
        self.logger.debug("Setting {} cooling set point to {}".format(self, target))
        enabled = self.cooling_enabled
        self._driver.set_temp_regulation(self._handle, target, enabled)

    @property
    def cooling_enabled(self):
        """
        Current status of the camera's image sensor cooling system (enabled/disabled).

        Can be set by assigning a bool.
        """
        temp_status = self._driver.query_temp_status(self._handle)
        return temp_status['cooling_enabled']

    @cooling_enabled.setter
    def cooling_enabled(self, enable):
        self.logger.debug("Setting {} cooling enabled to {}".format(self.name, enable))
        target = self.target_temperature
        self._driver.set_temp_regulation(self._handle, target, enable)

    @property
    def cooling_power(self):
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
        # No way to directly ask the camera whether it has image sensor cooling or not. Need to
        # check camera type and infer from that. As far as I can tell all models apart from the
        # ST-i range and the SG-4 (which isn't included in the SDK yet) have cooling.
        if self.properties['camera type'] != "STI_CAMERA":
            self._is_cooled_camera = True
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

        header.set('CAM-FW', self.properties['firmware version'], 'Camera firmware version')
        header.set('XPIXSZ', self.properties['readout modes'][readout_mode]['pixel width'].value,
                   'Microns')
        header.set('YPIXSZ', self.properties['readout modes'][readout_mode]['pixel height'].value,
                   'Microns')

        return header
