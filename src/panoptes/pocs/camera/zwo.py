"""ZWO ASI camera implementation using the ASICamera2 SDK.

Exposes a Camera class that wraps the ASIDriver to control cooled ZWO cameras,
including ROI/image type, binning, gain, bandwidth, cooling, single exposures,
and basic video capture.
"""

import threading
import time
from contextlib import suppress

import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.time import Time
from panoptes.utils import error
from panoptes.utils.utils import get_quantity_value

from panoptes.pocs.camera.libasi import ASIDriver
from panoptes.pocs.camera.sdk import AbstractSDKCamera


class Camera(AbstractSDKCamera):
    """ZWO ASI camera controlled via the ASICamera2 SDK.

    Provides convenience properties for ROI, binning, image type, gain, and
    bandwidth settings, and supports single exposures and basic video capture.
    """

    _driver = None  # Class variable to store the ASI driver interface
    _cameras = []  # Cache of camera string IDs
    _assigned_cameras = set()  # Camera string IDs already in use.

    def __init__(
        self,
        name: str = "ZWO ASI Camera",
        gain: int | None = 100,
        image_type: str | None = None,
        bandwidthoverload: float = 99,
        binning: int = 2,
        *args,
        **kwargs,
    ):
        """
        ZWO ASI Camera class

        Args:
            serial_number (str): camera serial number or user set ID (up to 8 bytes). See notes.
            gain (int, optional): gain setting, using camera's internal units. If not given
                the camera will use its current or default setting.
            image_type (str, optional): image format to use (one of 'RAW8', 'RAW16', 'RGB24'
                or 'Y8'). Default is to use 'RAW16' if supported by the camera, otherwise
                the camera's own default will be used.
            bandwidthoverload (int, optional): bandwidth overload setting in percent,
                default is 99.
            binning (int, optional): binning factor to use for the camera, default is 2,
                which is quad binning.
            *args, **kwargs: additional arguments to be passed to the parent classes.

        Notes:
            ZWO ASI cameras don't have a 'port', they only have a non-deterministic integer
            camera_ID and, probably, an 8 byte serial number. Optionally they also have an
            8 byte ID that can be written to the camera firmware by the user (using ASICap,
            or pocs.camera.libasi.ASIDriver.set_ID()). The camera should be identified by
            its serial number or, if it doesn't have one, by the user set ID.
        """
        kwargs["readout_time"] = kwargs.get("readout_time", 0.1)
        kwargs["timeout"] = kwargs.get("timeout", 5)
        # ZWO cameras cannot take internal darks (not even supported in the API yet).
        kwargs["internal_darks"] = kwargs.get("internal_darks", False)

        self._video_event = threading.Event()

        super().__init__(name, ASIDriver, *args, **kwargs)

        # Increase default temperature_tolerance for ZWO cameras because the
        # default value is too low for their temperature resolution.
        self.temperature_tolerance = kwargs.get("temperature_tolerance", 0.6 * u.Celsius)

        if gain:
            self.gain = gain

        if bandwidthoverload is not None:
            self.bandwidthoverload = bandwidthoverload

        if image_type:
            self.image_type = image_type
        else:
            # Take monochrome 12 bit raw images by default, if we can
            if "RAW16" in self.properties["supported_video_format"]:
                self.image_type = "RAW16"

        if binning is not None:
            self.binning = binning

        self.logger.info(f"{self} initialised")

    def __del__(self):
        """Attempt some clean up"""
        with suppress(AttributeError, TypeError):
            camera_ID = self._handle
            self._driver.close_camera(camera_ID)
            self.logger.debug(f"Closed ZWO camera {camera_ID}")
        super().__del__()

    # Properties
    @property
    def roi(self) -> dict:
        """Get the ROI of the camera, which includes the width, height, binning, and image_type."""
        roi_format = self._driver.get_roi_format(self._handle)
        return roi_format

    @property
    def image_type(self) -> str:
        """Current camera image type, one of 'RAW8', 'RAW16', 'Y8', 'RGB24'"""
        return self.roi.get("image_type")

    @image_type.setter
    def image_type(self, new_image_type: str):
        """Set the camera image type.

        Args:
            new_image_type (str): One of 'RAW8', 'RAW16', 'RGB24', or 'Y8'.

        Raises:
            ValueError: If the requested type is not supported by this camera.
        """
        if new_image_type not in self.properties["supported_video_format"]:
            msg = f"Image type '{new_image_type} not supported by {self.model}"
            self.logger.error(msg)
            raise ValueError(msg)
        roi_format = self.roi
        roi_format["image_type"] = new_image_type
        self._driver.set_roi_format(self._handle, **roi_format)

    @property
    def binning(self) -> int:
        """Current camera binning setting, either `1` (no binning) or `2` (binning)."""
        return self.roi.get("binning")

    @binning.setter
    def binning(self, new_binning: int):
        """Set camera binning (1 or 2) and adjust ROI accordingly.

        Args:
            new_binning (int): Desired binning factor. Must be supported by the camera.

        Raises:
            ValueError: If the requested binning is not supported.
        """
        if new_binning not in self.properties["supported_bins"]:
            msg = f"Binning '{new_binning}' not supported by {self.model}"
            self.logger.error(msg)
            raise ValueError(msg)
        roi_format = self.roi
        roi_format["binning"] = new_binning
        roi_format["width"] = roi_format["width"].to_value() // new_binning
        roi_format["height"] = roi_format["height"].to_value() // new_binning
        self.logger.debug(f"Setting binning to {new_binning}")

        try:
            self._driver.set_roi_format(self._handle, **roi_format)
        except Exception as e:
            self.logger.error(f"Failed to set binning '{new_binning}': {e}")

    @property
    def image_size(self) -> tuple[u.Quantity, u.Quantity]:
        """Current camera image size, either `(width, height)`."""
        width = self.roi.get("width")
        height = self.roi.get("height")

        return width, height

    @property
    def width(self) -> u.Quantity:
        """Current image width"""
        return self.image_size[0]

    @property
    def height(self) -> u.Quantity:
        """Current image height"""
        return self.image_size[1]

    @property
    def bit_depth(self):
        """ADC bit depth"""
        return self.properties["bit_depth"]

    @property
    def temperature(self):
        """Current temperature of the camera's image sensor"""
        return self._control_getter("TEMPERATURE")[0]

    @AbstractSDKCamera.target_temperature.getter
    def target_temperature(self):
        """Current value of the target temperature for the camera's image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity
        """
        return self._control_getter("TARGET_TEMP")[0]

    @AbstractSDKCamera.cooling_enabled.getter
    def cooling_enabled(self):
        """Current status of the camera's image sensor cooling system (enabled/disabled)"""
        return self._control_getter("COOLER_ON")[0]

    @property
    def cooling_power(self):
        """Current power level of the camera's image sensor cooling system (as a percentage)."""
        return self._control_getter("COOLER_POWER_PERC")[0]

    @property
    def gain(self):
        """Current value of the camera's gain setting in internal units.

        See `egain` for the corresponding electrons / ADU value.
        """
        return self._control_getter("GAIN")[0]

    @gain.setter
    def gain(self, gain):
        """Set the camera's internal gain value and refresh derived properties.

        Args:
            gain (int): Gain value in the camera's native units.
        """
        self._control_setter("GAIN", gain)
        self._refresh_info()  # This will update egain value in self.properties

    @property
    def egain(self):
        """Image sensor gain in e-/ADU for the current gain, as reported by the camera."""
        return self.properties["e_per_adu"]

    @property
    def is_exposing(self):
        """True if an exposure is currently under way, otherwise False"""
        return self._driver.get_exposure_status(self._handle) == "WORKING"

    @property
    def bandwidthoverload(self):
        """USB bandwidth usage limit as a percentage.

        Returns:
            int | float: The current bandwidth overload percentage.
        """
        return self._control_getter("BANDWIDTHOVERLOAD")[0]

    @bandwidthoverload.setter
    def bandwidthoverload(self, value):
        """Set the USB bandwidth overload percentage.

        Args:
            value (int | float | Quantity): Percentage (0–100). Quantities
                with units of percent are accepted.
        """
        value = get_quantity_value(value, u.percent) * u.percent
        self._control_setter("BANDWIDTHOVERLOAD", value)

    # Methods

    def connect(self, enable_cooling=False):
        """
        Connect to ZWO ASI camera.

        Gets 'camera_ID' (needed for all driver commands), camera properties and details
        of available camera commands/parameters.
        """
        self.logger.debug(f"Connecting to {self}")
        self._refresh_info()
        self._handle = self.properties["camera_ID"]
        self.model, _, _ = self.properties["name"].partition("(")
        if self.properties["has_cooler"]:
            self._is_cooled_camera = enable_cooling
        if self.properties["is_color_camera"]:
            self._filter_type = self.properties["bayer_pattern"]
        else:
            self._filter_type = "M"  # Monochrome
        self._driver.open_camera(self._handle)
        self._driver.init_camera(self._handle)
        self._control_info = self._driver.get_control_caps(self._handle)
        self._info["control_info"] = self._control_info  # control info accessible via properties
        self._driver.disable_dark_subtract(self._handle)
        self._connected = True

    def start_video(self, seconds, filename_root, max_frames, image_type=None):
        """Start video capture and write frames to FITS files.

        Args:
            seconds (float | Quantity): Exposure time per frame.
            filename_root (str): Prefix for output filenames (frame number appended).
            max_frames (int): Maximum number of frames to capture before stopping.
            image_type (str | None): Optional image type override (e.g., 'RAW16').
        """
        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second
        self._control_setter("EXPOSURE", seconds)
        if image_type:
            self.image_type = image_type

        roi_format = self._driver.get_roi_format(self._handle)
        width = int(get_quantity_value(roi_format["width"], unit=u.pixel))
        height = int(get_quantity_value(roi_format["height"], unit=u.pixel))
        image_type = roi_format["image_type"]

        timeout = 2 * seconds + self.timeout * u.second

        video_args = (
            width,
            height,
            image_type,
            timeout,
            filename_root,
            self.file_extension,
            int(max_frames),
            self._create_fits_header(seconds, dark=False),
        )
        video_thread = threading.Thread(target=self._video_readout, args=video_args, daemon=True)

        self._driver.start_video_capture(self._handle)
        self._video_event.clear()
        video_thread.start()
        self.logger.debug(f"Video capture started on {self}")

    def stop_video(self):
        """Stop video capture and signal the reader thread to finish."""
        self._video_event.set()
        self._driver.stop_video_capture(self._handle)
        self.logger.debug(f"Video capture stopped on {self}")

    # Private methods

    def _set_target_temperature(self, target):
        self._control_setter("TARGET_TEMP", target)
        self._target_temperature = target

    def _set_cooling_enabled(self, enable):
        self._control_setter("COOLER_ON", enable)

    def _video_readout(
        self, width, height, image_type, timeout, filename_root, file_extension, max_frames, header
    ):
        start_time = time.monotonic()
        good_frames = 0
        bad_frames = 0

        # Calculate number of bits that have been used to pad the raw data to RAW16 format.
        if self.image_type == "RAW16":
            pad_bits = 16 - int(get_quantity_value(self.bit_depth, u.bit))
        else:
            pad_bits = 0

        for frame_number in range(max_frames):
            if self._video_event.is_set():
                break
            # This call will block for up to timeout milliseconds waiting for a frame
            video_data = self._driver.get_video_data(self._handle, width, height, image_type, timeout)
            if video_data is not None:
                now = Time.now()
                header.set("DATE-OBS", now.fits, "End of exposure + readout")
                filename = f"{filename_root}_{frame_number:06d}.{file_extension}"
                # Fix 'raw' data scaling by changing from zero padding of LSBs
                # to zero padding of MSBs.
                video_data = np.right_shift(video_data, pad_bits)
                self.write_fits(video_data, header, filename)
                good_frames += 1
            else:
                bad_frames += 1

        if frame_number == max_frames - 1:
            # No one callled stop_video() before max_frames so have to call it here
            self.stop_video()

        elapsed_time = (time.monotonic() - start_time) * u.second
        self.logger.debug(
            f"Captured {good_frames} of {max_frames} frames in {elapsed_time:.2f} "
            f"({get_quantity_value(good_frames / elapsed_time):.2f} fps), "
            f"{bad_frames} frames lost"
        )

    def _start_exposure(self, seconds=None, filename=None, dark=False, header=None, *args, **kwargs):
        self._control_setter("EXPOSURE", seconds)
        roi_format = self._driver.get_roi_format(self._handle)
        self._driver.start_exposure(self._handle)
        readout_args = (filename, roi_format["width"], roi_format["height"], header)
        return readout_args

    def _readout(self, filename, width, height, header):
        exposure_status = self._driver.get_exposure_status(self._handle)
        if exposure_status == "SUCCESS":
            try:
                image_data = self._driver.get_exposure_data(self._handle, width, height, self.image_type)
            except RuntimeError as err:
                raise error.PanError(f"Error getting image data from {self}: {err}")
            else:
                # Fix 'raw' data scaling by changing from zero padding of LSBs
                # to zero padding of MSBs.
                if self.image_type == "RAW16":
                    pad_bits = 16 - int(get_quantity_value(self.bit_depth, u.bit))
                    image_data = np.right_shift(image_data, pad_bits)

                self.write_fits(data=image_data, header=header, filename=filename)
        elif exposure_status == "FAILED":
            raise error.PanError(f"Exposure failed on {self}")
        elif exposure_status == "IDLE":
            raise error.PanError(f"Exposure missing on {self}")
        else:
            raise error.PanError(f"Unexpected exposure status on {self}: '{exposure_status}'")

    def _create_fits_header(self, seconds, dark=None, metadata=None) -> fits.Header:
        header = super()._create_fits_header(seconds, dark)
        header.set("CAM-GAIN", self.gain, "Internal units")
        header.set("XPIXSZ", get_quantity_value(self.properties["pixel_size"], u.um), "Microns")
        header.set("YPIXSZ", get_quantity_value(self.properties["pixel_size"], u.um), "Microns")
        return header

    def _refresh_info(self):
        self._info = self._driver.get_camera_property(self._address)

    def _control_getter(self, control_type):
        if control_type in self._control_info:
            return self._driver.get_control_value(self._handle, control_type)
        else:
            raise error.NotSupported(f"{self.model} has no '{control_type}' parameter")

    def _control_setter(self, control_type, value):
        if control_type not in self._control_info:
            raise error.NotSupported(f"{self.model} has no '{control_type}' parameter")

        control_name = self._control_info[control_type]["name"]
        if not self._control_info[control_type]["is_writable"]:
            raise error.NotSupported(f"{self.model} cannot set {control_name} parameter'")

        if value != "AUTO":
            # Check limits.
            max_value = self._control_info[control_type]["max_value"]
            if value > max_value:
                self.logger.warning(
                    f"Cannot set {control_name} to {value}, clipping to max value: {max_value}."
                )
                self._driver.set_control_value(self._handle, control_type, max_value)
                return

            min_value = self._control_info[control_type]["min_value"]
            if value < min_value:
                self.logger.warning(
                    f"Cannot set {control_name} to {value}, clipping to min value: {min_value}."
                )
                self._driver.set_control_value(self._handle, control_type, min_value)
                return
        else:
            if not self._control_info[control_type]["is_auto_supported"]:
                raise error.IllegalValue(f"{self.model} cannot set {control_name} to AUTO")

        self._driver.set_control_value(self._handle, control_type, value)
