import time
import threading
from contextlib import suppress

import numpy as np
from astropy import units as u
from astropy.time import Time

from panoptes.pocs.camera.sdk import AbstractSDKCamera
from panoptes.pocs.camera.libasi import ASIDriver
from panoptes.utils.images import fits as fits_utils
from panoptes.utils import error
from panoptes.utils import get_quantity_value


class Camera(AbstractSDKCamera):

    _driver = None  # Class variable to store the ASI driver interface
    _cameras = []  # Cache of camera string IDs
    _assigned_cameras = set()  # Camera string IDs already in use.

    def __init__(self,
                 name='ZWO ASI Camera',
                 gain=None,
                 image_type=None,
                 *args, **kwargs):
        """
        ZWO ASI Camera class

        Args:
            serial_number (str): camera serial number or user set ID (up to 8 bytes). See notes.
            gain (int, optional): gain setting, using camera's internal units. If not given
                the camera will use its current or default setting.
            image_type (str, optional): image format to use (one of 'RAW8', 'RAW16', 'RGB24'
                or 'Y8'). Default is to use 'RAW16' if supported by the camera, otherwise
                the camera's own default will be used.
            *args, **kwargs: additional arguments to be passed to the parent classes.

        Notes:
            ZWO ASI cameras don't have a 'port', they only have a non-deterministic integer
            camera_ID and, probably, an 8 byte serial number. Optionally they also have an
            8 byte ID that can be written to the camera firmware by the user (using ASICap,
            or pocs.camera.libasi.ASIDriver.set_ID()). The camera should be identified by
            its serial number or, if it doesn't have one, by the user set ID.
        """
        kwargs['readout_time'] = kwargs.get('readout_time', 0.1)
        kwargs['timeout'] = kwargs.get('timeout', 0.5)

        self._video_event = threading.Event()

        super().__init__(name, ASIDriver, *args, **kwargs)

        # Increase default temperature_tolerance for ZWO cameras because the
        # default value is too low for their temperature resolution.
        self.temperature_tolerance = kwargs.get('temperature_tolerance', 0.6 * u.Celsius)

        if gain:
            self.gain = gain

        if image_type:
            self.image_type = image_type
        else:
            # Take monochrome 12 bit raw images by default, if we can
            if 'RAW16' in self.properties['supported_video_format']:
                self.image_type = 'RAW16'

        self.logger.info('{} initialised'.format(self))

    def __del__(self):
        """ Attempt some clean up """
        with suppress(AttributeError):
            camera_ID = self._handle
            Camera._driver.close_camera(camera_ID)
            self.logger.debug("Closed ZWO camera {}".format(camera_ID))
        super().__del__()

    # Properties

    @property
    def image_type(self):
        """ Current camera image type, one of 'RAW8', 'RAW16', 'Y8', 'RGB24' """
        roi_format = Camera._driver.get_roi_format(self._handle)
        return roi_format['image_type']

    @image_type.setter
    def image_type(self, new_image_type):
        if new_image_type not in self.properties['supported_video_format']:
            msg = "Image type '{} not supported by {}".format(new_image_type, self.model)
            self.logger.error(msg)
            raise ValueError(msg)
        roi_format = self._driver.get_roi_format(self._handle)
        roi_format['image_type'] = new_image_type
        Camera._driver.set_roi_format(self._handle, **roi_format)

    @property
    def bit_depth(self):
        """ADC bit depth"""
        return self.properties['bit_depth']

    @property
    def temperature(self):
        """ Current temperature of the camera's image sensor """
        return self._control_getter('TEMPERATURE')[0]

    @property
    def target_temperature(self):
        """ Current value of the target temperature for the camera's image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity
        """
        return self._control_getter('TARGET_TEMP')[0]

    @target_temperature.setter
    def target_temperature(self, target):
        if not isinstance(target, u.Quantity):
            target = target * u.Celsius
        self.logger.debug("Setting {} cooling set point to {}".format(self, target))
        self._control_setter('TARGET_TEMP', target)

    @property
    def cooling_enabled(self):
        """ Current status of the camera's image sensor cooling system (enabled/disabled) """
        return self._control_getter('COOLER_ON')[0]

    @cooling_enabled.setter
    def cooling_enabled(self, enable):
        self._control_setter('COOLER_ON', enable)

    @property
    def cooling_power(self):
        """ Current power level of the camera's image sensor cooling system (as a percentage). """
        return self._control_getter('COOLER_POWER_PERC')[0]

    @property
    def gain(self):
        """ Current value of the camera's gain setting in internal units.

        See `egain` for the corresponding electrons / ADU value.
        """
        return self._control_getter('GAIN')[0]

    @gain.setter
    def gain(self, gain):
        self._control_setter('GAIN', gain)
        self._refresh_info()  # This will update egain value in self.properties

    @property
    def egain(self):
        """ Image sensor gain in e-/ADU for the current gain, as reported by the camera."""
        return self.properties['e_per_adu']

    @property
    def is_exposing(self):
        """ True if an exposure is currently under way, otherwise False """
        return Camera._driver.get_exposure_status(self._handle) == "WORKING"

    # Methods

    def connect(self):
        """
        Connect to ZWO ASI camera.

        Gets 'camera_ID' (needed for all driver commands), camera properties and details
        of available camera commands/parameters.
        """
        self.logger.debug("Connecting to {}".format(self))
        self._refresh_info()
        self._handle = self.properties['camera_ID']
        self.model, _, _ = self.properties['name'].partition('(')
        if self.properties['has_cooler']:
            self._is_cooled_camera = True
        if self.properties['is_color_camera']:
            self._filter_type = self.properties['bayer_pattern']
        else:
            self._filter_type = 'M'  # Monochrome
        Camera._driver.open_camera(self._handle)
        Camera._driver.init_camera(self._handle)
        self._control_info = Camera._driver.get_control_caps(self._handle)
        self._info['control_info'] = self._control_info  # control info accessible via properties
        Camera._driver.disable_dark_subtract(self._handle)
        self._connected = True

    def start_video(self, seconds, filename_root, max_frames, image_type=None):
        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second
        self._control_setter('EXPOSURE', seconds)
        if image_type:
            self.image_type = image_type

        roi_format = Camera._driver.get_roi_format(self._handle)
        width = int(get_quantity_value(roi_format['width'], unit=u.pixel))
        height = int(get_quantity_value(roi_format['height'], unit=u.pixel))
        image_type = roi_format['image_type']

        timeout = 2 * seconds + self._timeout * u.second

        video_args = (width,
                      height,
                      image_type,
                      timeout,
                      filename_root,
                      self.file_extension,
                      int(max_frames),
                      self._create_fits_header(seconds, dark=False))
        video_thread = threading.Thread(target=self._video_readout,
                                        args=video_args,
                                        daemon=True)

        Camera._driver.start_video_capture(self._handle)
        self._video_event.clear()
        video_thread.start()
        self.logger.debug("Video capture started on {}".format(self))

    def stop_video(self):
        self._video_event.set()
        Camera._driver.stop_video_capture(self._handle)
        self.logger.debug("Video capture stopped on {}".format(self))

    # Private methods

    def _video_readout(self,
                       width,
                       height,
                       image_type,
                       timeout,
                       filename_root,
                       file_extension,
                       max_frames,
                       header):

        start_time = time.monotonic()
        good_frames = 0
        bad_frames = 0

        # Calculate number of bits that have been used to pad the raw data to RAW16 format.
        if self.image_type == 'RAW16':
            pad_bits = 16 - int(get_quantity_value(self.bit_depth, u.bit))
        else:
            pad_bits = 0

        for frame_number in range(max_frames):
            if self._video_event.is_set():
                break
            # This call will block for up to timeout milliseconds waiting for a frame
            video_data = Camera._driver.get_video_data(self._handle,
                                                       width,
                                                       height,
                                                       image_type,
                                                       timeout)
            if video_data is not None:
                now = Time.now()
                header.set('DATE-OBS', now.fits, 'End of exposure + readout')
                filename = "{}_{:06d}.{}".format(filename_root, frame_number, file_extension)
                # Fix 'raw' data scaling by changing from zero padding of LSBs
                # to zero padding of MSBs.
                video_data = np.right_shift(video_data, pad_bits)
                fits_utils.write_fits(video_data, header, filename)
                good_frames += 1
            else:
                bad_frames += 1

        if frame_number == max_frames - 1:
            # No one callled stop_video() before max_frames so have to call it here
            self.stop_video()

        elapsed_time = (time.monotonic() - start_time) * u.second
        self.logger.debug("Captured {} of {} frames in {:.2f} ({:.2f} fps), {} frames lost".format(
            good_frames,
            max_frames,
            elapsed_time,
            get_quantity_value(good_frames / elapsed_time),
            bad_frames))

    def _start_exposure(self, seconds, filename, dark, header, *args, **kwargs):
        self._control_setter('EXPOSURE', seconds)
        roi_format = Camera._driver.get_roi_format(self._handle)
        Camera._driver.start_exposure(self._handle)
        readout_args = (filename,
                        roi_format['width'],
                        roi_format['height'],
                        header)
        return readout_args

    def _readout(self, filename, width, height, header):
        exposure_status = Camera._driver.get_exposure_status(self._handle)
        if exposure_status == 'SUCCESS':
            try:
                image_data = Camera._driver.get_exposure_data(self._handle,
                                                              width,
                                                              height,
                                                              self.image_type)
            except RuntimeError as err:
                raise error.PanError('Error getting image data from {}: {}'.format(self, err))
            else:
                # Fix 'raw' data scaling by changing from zero padding of LSBs
                # to zero padding of MSBs.
                if self.image_type == 'RAW16':
                    pad_bits = 16 - int(get_quantity_value(self.bit_depth, u.bit))
                    image_data = np.right_shift(image_data, pad_bits)

                fits_utils.write_fits(image_data,
                                      header,
                                      filename,
                                      self.logger)
        elif exposure_status == 'FAILED':
            raise error.PanError("Exposure failed on {}".format(self))
        elif exposure_status == 'IDLE':
            raise error.PanError("Exposure missing on {}".format(self))
        else:
            raise error.PanError("Unexpected exposure status on {}: '{}'".format(
                self, exposure_status))

    def _create_fits_header(self, seconds, dark):
        header = super()._create_fits_header(seconds, dark)
        header.set('CAM-GAIN', self.gain, 'Internal units')
        header.set('XPIXSZ', get_quantity_value(self.properties['pixel_size'], u.um), 'Microns')
        header.set('YPIXSZ', get_quantity_value(self.properties['pixel_size'], u.um), 'Microns')
        return header

    def _refresh_info(self):
        self._info = Camera._driver.get_camera_property(self._address)

    def _control_getter(self, control_type):
        if control_type in self._control_info:
            return Camera._driver.get_control_value(self._handle, control_type)
        else:
            raise error.NotSupported("{} has no '{}' parameter".format(self.model, control_type))

    def _control_setter(self, control_type, value):
        if control_type not in self._control_info:
            raise error.NotSupported("{} has no '{}' parameter".format(self.model, control_type))

        control_name = self._control_info[control_type]['name']
        if not self._control_info[control_type]['is_writable']:
            raise error.NotSupported("{} cannot set {} parameter'".format(
                self.model, control_name))

        if value != 'AUTO':
            # Check limits.
            max_value = self._control_info[control_type]['max_value']
            if value > max_value:
                msg = "Cannot set {} to {}, clipping to max value {}".format(
                    control_name, value, max_value)
                Camera._driver.set_control_value(self._handle, control_type, max_value)
                raise error.IllegalValue(msg)

            min_value = self._control_info[control_type]['min_value']
            if value < min_value:
                msg = "Cannot set {} to {}, clipping to min value {}".format(
                    control_name, value, min_value)
                Camera._driver.set_control_value(self._handle, control_type, min_value)
                raise error.IllegalValue(msg)
        else:
            if not self._control_info[control_type]['is_auto_supported']:
                msg = "{} cannot set {} to AUTO".format(self.model, control_name)
                raise error.IllegalValue(msg)

        Camera._driver.set_control_value(self._handle, control_type, value)
