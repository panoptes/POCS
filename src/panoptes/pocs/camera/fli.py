from contextlib import suppress

import numpy as np

from astropy import units as u

from panoptes.pocs.camera.sdk import AbstractSDKCamera
from panoptes.pocs.camera.libfli import FLIDriver
from panoptes.pocs.camera import libfliconstants as c
from panoptes.utils.images import fits as fits_utils
from panoptes.utils import error


class Camera(AbstractSDKCamera):
    _driver = None
    _cameras = {}
    _assigned_cameras = set()

    def __init__(self,
                 name='FLI Camera',
                 target_temperature=25 * u.Celsius,
                 *args, **kwargs):
        kwargs['target_temperature'] = target_temperature
        super().__init__(name, FLIDriver, *args, **kwargs)
        self.logger.info('{} initialised'.format(self))

    def __del__(self):
        with suppress(AttributeError):
            handle = self._handle
            self._driver.FLIClose(handle)
            self.logger.debug('Closed FLI camera handle {}'.format(handle.value))
        super().__del__()

# Properties

    @property
    def temperature(self):
        """
        Current temperature of the camera's image sensor.
        """
        return self._driver.FLIGetTemperature(self._handle)

    @property
    def target_temperature(self):
        """
        Current value of the target temperature for the camera's image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity.
        """
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, target):
        if not isinstance(target, u.Quantity):
            target = target * u.Celsius
        self.logger.debug("Setting {} cooling set point to {}".format(self, target))
        self._driver.FLISetTemperature(self._handle, target)
        self._target_temperature = target

    @property
    def cooling_enabled(self):
        """
        Current status of the camera's image sensor cooling system (enabled/disabled).

        Note: For FLI cameras this is always True, and cannot be set.
        """
        return True

    @cooling_enabled.setter
    def cooling_enabled(self, enable):
        # Cooling is always enabled on FLI cameras
        if not enable:
            raise error.NotSupported("Cannot disable cooling on {}".format(self.name))

    @property
    def cooling_power(self):
        """
        Current power level of the camera's image sensor cooling system (as
        a percentage of the maximum).
        """
        return self._driver.FLIGetCoolerPower(self._handle)

    @property
    def is_exposing(self):
        """ True if an exposure is currently under way, otherwise False """
        return bool(self._driver.FLIGetExposureStatus(self._handle).value)

# Methods

    def connect(self):
        """
        Connect to FLI camera.

        Gets a 'handle', serial number and specs/capabilities from the driver
        """
        self.logger.debug('Connecting to {}'.format(self))
        self._handle = self._driver.FLIOpen(port=self._address)
        if self._handle == c.FLI_INVALID_DEVICE:
            message = 'Could not connect to {} on {}!'.format(self.name, self._camera_address)
            raise error.PanError(message)
        self._get_camera_info()
        self.model = self.properties['camera model']
        # All FLI camera models are cooled
        self._is_cooled_camera = True
        self._connected = True

# Private Methods

    def _start_exposure(self, seconds, filename, dark, header, *args, **kwargs):
        self._driver.FLISetExposureTime(self._handle, exposure_time=seconds)

        if dark:
            frame_type = c.FLI_FRAME_TYPE_DARK
        else:
            frame_type = c.FLI_FRAME_TYPE_NORMAL
        self._driver.FLISetFrameType(self._handle, frame_type)

        # For now set to 'visible' (i.e. light sensitive) area of image sensor.
        # Can later use this for windowed exposures.
        self._driver.FLISetImageArea(self._handle,
                                     self.properties['visible corners'][0],
                                     self.properties['visible corners'][1])

        # No on chip binning for now.
        self._driver.FLISetHBin(self._handle, bin_factor=1)
        self._driver.FLISetVBin(self._handle, bin_factor=1)

        # No pre-exposure image sensor flushing, either.
        self._driver.FLISetNFlushes(self._handle, n_flushes=0)

        # In principle can set bit depth here (16 or 8 bit) but most FLI cameras don't support it.

        # Start exposure
        self._driver.FLIExposeFrame(self._handle)

        readout_args = (filename,
                        self.properties['visible width'],
                        self.properties['visible height'],
                        header)
        return readout_args

    def _readout(self, filename, width, height, header):
        # Use FLIGrabRow for now at least because I can't get FLIGrabFrame to work.
        # image_data = self._FLIDriver.FLIGrabFrame(self._handle, width, height)
        image_data = np.zeros((height, width), dtype=np.uint16)
        rows_got = 0
        try:
            for i in range(image_data.shape[0]):
                image_data[i] = self._driver.FLIGrabRow(self._handle, image_data.shape[1])
                rows_got += 1
        except RuntimeError as err:
            message = 'Readout error on {}, expected {} rows, got {}: {}'.format(
                self, image_data.shape[0], rows_got, err)
            raise error.PanError(message)
        else:
            fits_utils.write_fits(image_data, header, filename)

    def _create_fits_header(self, seconds, dark):
        header = super()._create_fits_header(seconds, dark)

        header.set('CAM-HW', self.properties['hardware version'], 'Camera hardware version')
        header.set('CAM-FW', self.properties['firmware version'], 'Camera firmware version')
        header.set('XPIXSZ', self.properties['pixel width'].value, 'Microns')
        header.set('YPIXSZ', self.properties['pixel height'].value, 'Microns')

        return header

    def _get_camera_info(self):

        serial_number = self._driver.FLIGetSerialString(self._handle)
        camera_model = self._driver.FLIGetModel(self._handle)
        hardware_version = self._driver.FLIGetHWRevision(self._handle)
        firmware_version = self._driver.FLIGetFWRevision(self._handle)

        pixel_width, pixel_height = self._driver.FLIGetPixelSize(self._handle)
        ccd_corners = self._driver.FLIGetArrayArea(self._handle)
        visible_corners = self._driver.FLIGetVisibleArea(self._handle)

        self._info = {
            'serial number': serial_number,
            'camera model': camera_model,
            'hardware version': hardware_version,
            'firmware version': firmware_version,
            'pixel width': pixel_width,
            'pixel height': pixel_height,
            'array corners': ccd_corners,
            'array height': ccd_corners[1][1] - ccd_corners[0][1],
            'array width': ccd_corners[1][0] - ccd_corners[0][0],
            'visible corners': visible_corners,
            'visible height': visible_corners[1][1] - visible_corners[0][1],
            'visible width': visible_corners[1][0] - visible_corners[0][0]
        }
