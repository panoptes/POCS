import ctypes
import enum

import numpy as np
from astropy import units as u

from panoptes.pocs.camera.sdk import AbstractSDKDriver
from panoptes.utils import error
from panoptes.utils import get_quantity_value

####################################################################################################
#
# Main ASI Driver class.
#
# The methods of this class call the functions fron ASICamera2.h using the ctypes foreign function
# library. Based on v1.13.0930 of the ZWO ASI SDK.
#
####################################################################################################


class ASIDriver(AbstractSDKDriver):
    def __init__(self, library_path=None, **kwargs):
        """Main class representing the ZWO ASI library interface.

        On construction loads the shared object/dynamically linked version of the ASI SDK library,
        which must be already installed (see https://astronomy-imaging-camera.com/software-drivers).

        The name and location of the shared library can be manually specified with the library_path
        argument, otherwise the ctypes.util.find_library function will be used to try to locate it.

        Args:
            library_path (str, optional): path to the library e.g. '/usr/local/lib/libASICamera2.so'

        Returns:
            `~pocs.camera.libasi.ASIDriver`

        Raises:
            panoptes.utils.error.NotFound: raised if library_path not given & find_libary fails to
                locate the library.
            OSError: raises if the ctypes.CDLL loader cannot load the library.
        """
        super().__init__(name='ASICamera2', library_path=library_path, **kwargs)
        self._product_ids = self.get_product_ids()  # Supported camera models
    # Methods

    def get_SDK_version(self):
        """ Get the version of the ZWO ASI SDK """
        # First set return type for function to pointer to null terminated string
        self._CDLL.ASIGetSDKVersion.restype = ctypes.c_char_p
        version = self._CDLL.ASIGetSDKVersion().decode('ascii')  # Get bytes so decode to str
        version = version.replace(', ', '.')  # Format the version string properly
        return version

    def get_devices(self):
        """Gets currently connected camera info.

        Returns:
            dict: All currently connected camera serial numbers with corresponding integer
                camera IDs.

        Notes:
            If a camera does not have a serial number it will attempt to fall back to string ID.
            Cameras with neither serial number nor string ID will be left out of the dictionary
            as they have no unique indentifier.
        """
        n_cameras = self.get_num_of_connected_cameras()
        if n_cameras == 0:
            raise error.PanError("No ZWO ASI camera devices found")

        # Get the IDs
        cameras = {}
        for camera_index in range(n_cameras):
            info = self.get_camera_property(camera_index)
            camera_ID = info['camera_ID']
            self.open_camera(camera_ID)
            try:
                serial_number = self.get_serial_number(camera_ID)
            except RuntimeError as err:
                # If at first you don't succeed, try, except, else, finally again.
                self.logger.warning(f"Error getting serial number: {err}")
                try:
                    string_ID = self.get_ID(camera_ID)
                except RuntimeError as err:
                    self.logger.warning(f"Error getting string ID: {err}")
                    msg = f"Skipping ZWO ASI camera {camera_ID} with no serial number or string ID."
                    self.logger.error(msg)
                    break
                else:
                    msg = f"Using string ID '{string_ID}' in place of serial number."
                    self.logger.warning(msg)
                    serial_number = string_ID
            finally:
                self.close_camera(camera_ID)

            cameras[serial_number] = camera_ID
        self.logger.debug(f"Got camera serial numbers: {list(cameras.keys())}")
        return cameras

    def get_num_of_connected_cameras(self):
        """ Get the count of connected ASI cameras """
        count = self._CDLL.ASIGetNumOfConnectedCameras()  # Return type is int, needs no Pythonising
        self.logger.debug("Found {} connected ASI cameras".format(count))
        return count

    def get_product_ids(self):
        """Get product IDs of cameras supported by the SDK."""
        n_pids = self._CDLL.ASIGetProductIDs(0)  # Call once to get number of product IDs
        if n_pids > 0:
            # Make array of C ints of required size.
            product_ids = (ctypes.c_int * n_pids)()
            # Call again to get product IDs. Should get same n_pids as before.
            assert n_pids == self._CDLL.ASIGetProductIDs(ctypes.byref(product_ids))
        else:
            self.logger.error("Error getting supported camera product IDs from SDK.")
            raise RuntimeError("ZWO SDK support 0 SDK products?")

        self.logger.debug("Got {} supported camera product IDs from SDK.".format(n_pids))
        return list(product_ids)

    def get_camera_property(self, camera_index):
        """ Get properties of the camera with given index """
        camera_info = CameraInfo()
        error_code = self._CDLL.ASIGetCameraProperty(ctypes.byref(camera_info), camera_index)
        if error_code != ErrorCode.SUCCESS:
            msg = "Error calling ASIGetCameraProperty: {}".format(ErrorCode(error_code).name)
            self.logger.error(msg)
            raise RuntimeError(msg)

        pythonic_info = self._parse_info(camera_info)
        self.logger.debug("Got info from camera {camera_ID}, {name}".format(**pythonic_info))
        return pythonic_info

    def get_camera_property_by_id(self, camera_ID):
        """Get properties of the camera with a given integer ID."""
        camera_info = CameraInfo()
        self._call_function('ASIGetCameraPropertyByID',
                            camera_ID,
                            ctypes.byref(camera_info))

        pythonic_info = self._parse_info(camera_info)
        self.logger.debug("Got info from camera {camera_ID}, {name}".format(**pythonic_info))
        return pythonic_info

    def open_camera(self, camera_ID):
        """ Open camera with given integer ID """
        self._call_function('ASIOpenCamera', camera_ID)
        self.logger.debug("Opened camera {}".format(camera_ID))

    def init_camera(self, camera_ID):
        """ Initialise camera with given integer ID """
        self._call_function('ASIInitCamera', camera_ID)
        self.logger.debug("Initialised camera {}".format(camera_ID))

    def close_camera(self, camera_ID):
        """ Close camera with given integer ID """
        self._call_function('ASICloseCamera', camera_ID)
        self.logger.debug("Closed camera {}".format(camera_ID))

    def get_ID(self, camera_ID):
        """Get string ID from firmaware for the camera with given integer ID

        The saved ID is an array of 8 unsigned chars for some reason.
        """
        struct_ID = ID()
        self._call_function('ASIGetID', camera_ID, ctypes.byref(struct_ID))
        bytes_ID = bytes(struct_ID.id)
        string_ID = bytes_ID.decode()
        self.logger.debug("Got string ID '{}' from camera {}".format(string_ID, camera_ID))
        return string_ID

    def set_ID(self, camera_ID, string_ID):
        """Save string ID to firmware of camera with given integer ID

        The saved ID is an array of 8 unsigned chars for some reason. To preserve some sanity
        this method takes an 8 byte UTF-8 string as input.
        """
        bytes_ID = string_ID.encode()  # Convert string to bytes
        if len(bytes_ID) > 8:
            bytes_ID = bytes_ID[:8]  # This may chop out part of a UTF-8 multibyte character
            self.logger.warning("New ID longer than 8 bytes, truncating {} to {}".format(
                string_ID, bytes_ID.decode()))
        else:
            bytes_ID = bytes_ID.ljust(8)  # Pad to 8 bytes with spaces, if necessary
        uchar_ID = (ctypes.c_ubyte * 8).from_buffer_copy(bytes_ID)
        self._call_function('ASISetID', camera_ID, ID(uchar_ID))
        self.logger.debug("Set camera {} string ID to '{}'".format(camera_ID, bytes_ID.decode()))

    def get_num_of_controls(self, camera_ID):
        """ Gets the number of control types supported by the camera with given integer ID """
        n_controls = ctypes.c_int()
        self._call_function('ASIGetNumOfControls', camera_ID, ctypes.byref(n_controls))
        n_controls = n_controls.value  # Convert from ctypes c_int type to Python int
        self.logger.debug("Camera {} has {} controls".format(camera_ID, n_controls))
        return n_controls

    def get_control_caps(self, camera_ID):
        """ Gets the details of all the controls supported by the camera with given integer ID """
        n_controls = self.get_num_of_controls(camera_ID)  # First get number of controls
        controls = {}
        for i in range(n_controls):
            control_caps = ControlCaps()
            self._call_function('ASIGetControlCaps',
                                camera_ID,
                                ctypes.c_int(i),
                                ctypes.byref(control_caps))
            control = self._parse_caps(control_caps)
            controls[control['control_type']] = control
        self.logger.debug("Got details of {} controls from camera {}".format(n_controls, camera_ID))
        return controls

    def get_control_value(self, camera_ID, control_type):
        """ Gets the value of the control control_type from camera with given integer ID """
        value = ctypes.c_long()
        is_auto = ctypes.c_int()
        self._call_function('ASIGetControlValue',
                            camera_ID,
                            ControlType[control_type],
                            ctypes.byref(value),
                            ctypes.byref(is_auto))
        nice_value = self._parse_return_value(value, control_type)
        return nice_value, bool(is_auto)

    def set_control_value(self, camera_ID, control_type, value):
        """ Sets the value of the control control_type on camera with given integet ID """
        if value == 'AUTO':
            # Apparently need to pass current value when turning auto on
            auto = True
            value = self.get_control_value(camera_ID, control_type)[0]
        else:
            auto = False
        self._call_function('ASISetControlValue',
                            camera_ID,
                            ctypes.c_int(ControlType[control_type]),
                            self._parse_input_value(value, control_type),
                            ctypes.c_int(auto))
        self.logger.debug("Set {} to {} on camera {}".format(control_type,
                                                             'AUTO' if auto else value,
                                                             camera_ID))

    def get_roi_format(self, camera_ID):
        """ Get the ROI size and image format setting for camera with given integer ID """
        width = ctypes.c_int()
        height = ctypes.c_int()
        binning = ctypes.c_int()
        image_type = ctypes.c_int()
        self._call_function('ASIGetROIFormat',
                            camera_ID,
                            ctypes.byref(width),
                            ctypes.byref(height),
                            ctypes.byref(binning),
                            ctypes.byref(image_type))
        roi_format = {'width': width.value * u.pixel,
                      'height': height.value * u.pixel,
                      'binning': binning.value,
                      'image_type': ImgType(image_type.value).name}
        return roi_format

    def set_roi_format(self, camera_ID, width, height, binning, image_type):
        """ Set the ROI size and image format settings for the camera with given integer ID """
        width = int(get_quantity_value(width, unit=u.pixel))
        height = int(get_quantity_value(height, unit=u.pixel))
        binning = int(binning)
        self._call_function('ASISetROIFormat',
                            camera_ID,
                            ctypes.c_int(width),
                            ctypes.c_int(height),
                            ctypes.c_int(binning),
                            ctypes.c_int(ImgType[image_type]))
        self.logger.debug("Set ROI, format on camera {} to {}x{}/{}, {}".format(
            camera_ID, width, height, binning, image_type))

    def get_start_position(self, camera_ID):
        """ Get position of the upper left corner of the ROI for camera with given integer ID

        Args:
            camera_ID (int): integer ID of the camera

        Returns:
            (astropy.units.Quantity, astropy.units.Quantity): x, y coordinates of the upper left
                corner of the ROI. Note, these are in binned pixels.
        """
        start_x = ctypes.c_int()
        start_y = ctypes.c_int()
        self._call_function('ASIGetStartPos',
                            camera_ID,
                            ctypes.byref(start_x),
                            ctypes.byref(start_y))
        start_x = start_x.value * u.pixel
        start_y = start_y.value * u.pixel
        return start_x, start_y

    def set_start_position(self, camera_ID, start_x, start_y):
        """ Set position of the upper left corner of the ROI for camera with given integer ID """
        start_x = int(get_quantity_value(start_x, unit=u.pixel))
        start_y = int(get_quantity_value(start_y, unit=u.pixel))
        self._call_function('ASISetStartPos',
                            camera_ID,
                            ctypes.c_int(start_x),
                            ctypes.c_int(start_y))
        self.logger.debug("Set ROI start position of camera {} to ({}, {})".format(
            camera_ID, start_x, start_y))

    def get_dropped_frames(self, camera_ID):
        """Get the number of dropped frames during video capture."""
        n_dropped_frames = ctypes.c_int()
        self._call_function('ASIGetDroppedFrames',
                            camera_ID,
                            ctypes.byref(n_dropped_frames))
        self.logger_debug("Camera {} has dropped {} frames.".format(camera_ID, n_dropped_frames))
        return n_dropped_frames

    def enable_dark_subtract(self, camera_ID, dark_file_path):
        """Enable dark subtraction (not implemented).

        You almost certainly wouldn't want to use this as it only works with images taken in
        RGB8 format and only with dark frames saved as .BMP files. Far better to do dark
        subtraction in post-processing.
        """
        raise NotImplementedError

    def disable_dark_subtract(self, camera_ID):
        """Disable dark subtraction.

        May need to call this as dark current subtraction settings persist in the registry
        on Windows.
        """
        self._call_function('ASIDisableDarkSubtract',
                            camera_ID)
        self.logger.debug("Dark subtraction on camera {} disabled.".format(camera_ID))

    def pulse_guide_on(self, camera_ID, direction):
        """Turn on PulseGuide on ST4 port of given camera in given direction."""
        self._call_function('ASIPulseGuideOn',
                            camera_ID,
                            GuideDirection[direction])
        dname = GuideDirection[direction].name
        msg = f"PulseGuide on camera {camera_ID} on in direction {dname}."
        self.logger.debug(msg)

    def pulse_guide_off(self, camera_ID, direction):
        """Turn off PulseGuide on ST4 port of given camera in given direction."""
        self._call_function('ASIPulseGuideOff',
                            camera_ID,
                            GuideDirection[direction])
        dname = GuideDirection[direction].name
        msg = f"PulseGuide on camera {camera_ID} off in direction {dname}."
        self.logger.debug(msg)

    def get_gain_offset(self, camera_ID):
        """Get pre-setting parameters."""
        offset_highest_dr = ctypes.c_int()
        offset_unity_gain = ctypes.c_int()
        gain_lowest_rn = ctypes.c_int()
        offset_lowest_rn = ctypes.c_int()
        self._call_function('ASIGetGainOffset',
                            camera_ID,
                            ctypes.byref(offset_highest_dr),
                            ctypes.byref(offset_unity_gain),
                            ctypes.byref(gain_lowest_rn),
                            ctypes.byref(offset_lowest_rn))
        self.logger.debug('Got pre-setting parameters from camera {}.'.format(camera_ID))
        return offset_highest_dr, offset_unity_gain, gain_lowest_rn, offset_lowest_rn

    def get_camera_supported_mode(self, camera_ID):
        """Get supported trigger modes for camera with given integer ID."""
        modes_struct = SupportedMode()
        self._call_function('ASIGetCameraSupportMode',
                            camera_ID,
                            ctypes.byref(modes_struct.modes))
        supported_modes = []
        for mode_int in modes_struct.modes:
            if mode_int == CameraMode.END:
                break
            supported_modes.append(CameraMode(mode_int).name)

        self.logger.debug("Got supported modes {} for camera {}".format(supported_modes,
                                                                        camera_ID))
        return supported_modes

    def get_camera_mode(self, camera_ID):
        """Get current trigger mode for camera with given integer ID."""
        mode = ctypes.int()
        self._call_function('ASIGetCameraMode',
                            camera_ID,
                            ctypes.byref(mode))
        mode_name = CameraMode(mode).name
        self.logger.debug('Camera {} is in trigger mode {}'.format(camera_ID, mode_name))
        return mode_name

    def set_camera_mode(self, camera_ID, mode_name):
        """Set trigger mode for camera with given integer ID."""
        mode = CameraMode[mode_name]
        self._call_function('ASISetCameraMode',
                            camera_ID,
                            mode)
        self.logger.debug('Set trigger mode of camera {} to {}.'.format(camera_ID, mode_name))

    def send_soft_trigger(self, camera_ID, start_stop_signal):
        """Send out a soft trigger on camera with given integer ID."""
        self._call_function('ASISendSoftTrigger',
                            camera_ID,
                            int(bool(start_stop_signal)))
        self.logger.debug('Soft trigger sent to camera {}.'.format(camera_ID))

    def get_serial_number(self, camera_ID):
        """Get serial number of the camera with given integer ID.

        The serial number is an array of 8 unsigned chars, the same as string ID,
        but it is interpreted differently. It is displayed in ASICAP as a 16 digit
        hexadecimal number, so we will convert it the same 16 character string
        representation.
        """
        struct_SN = ID()  # Same structure as string ID.
        self._call_function('ASIGetSerialNumber',
                            camera_ID,
                            ctypes.byref(struct_SN))
        bytes_SN = bytes(struct_SN.id)
        serial_number = "".join(f"{b:02x}" for b in bytes_SN)
        self.logger.debug("Got serial number '{}' from camera {}".format(serial_number, camera_ID))
        return serial_number

    def get_trigger_output_io_conf(self, camera_ID):
        """Get external trigger configuration of the camera with given integer ID."""
        pin = ctypes.c_int()
        pin_high = ctypes.c_int()
        delay = ctypes.c_long()
        duration = ctypes.c_long()
        self._call_function('ASIGetTriggerOutputIOConf',
                            camera_ID,
                            ctypes.byref(pin),
                            ctypes.bytef(pin_high),
                            ctypes.byref(delay),
                            ctypes.byref(duration))
        self.logger.debug("Got trigger config from camera {}".format(camera_ID))
        return TrigOutput(pin).name, bool(pin_high), int(delay), int(duration)

    def set_trigger_ouput_io_conf(self, camera_ID, pin, pin_high, delay, duration):
        """Set external trigger configuration of the camera with given integer ID."""
        self._call_function('ASISetTriggerOutputIOConf',
                            camera_ID,
                            TrigOutput[pin],
                            ctypes.c_int(pin_high),
                            ctypes.c_long(delay),
                            ctypes.c_long(duration))
        self.logger.debug("Set trigger config of camera {}".format(camera_ID))

    def start_exposure(self, camera_ID):
        """ Start exposure on the camera with given integer ID """
        self._call_function('ASIStartExposure', camera_ID)
        self.logger.debug("Exposure started on camera {}".format(camera_ID))

    def stop_exposure(self, camera_ID):
        """ Cancel current exposure on camera with given integer ID """
        self._call_function('ASIStopExposure', camera_ID)
        self.logger.debug("Exposure on camera {} cancelled".format(camera_ID))

    def get_exposure_status(self, camera_ID):
        """ Get status of current exposure on camera with given integer ID """
        status = ctypes.c_int()
        self._call_function('ASIGetExpStatus', camera_ID, ctypes.byref(status))
        return ExposureStatus(status.value).name

    def get_exposure_data(self, camera_ID, width, height, image_type):
        """ Get image data from exposure on camera with given integer ID """
        exposure_data = self._image_array(width, height, image_type)

        self._call_function('ASIGetDataAfterExp',
                            camera_ID,
                            exposure_data.ctypes.data_as(ctypes.POINTER(ctypes.c_byte)),
                            ctypes.c_long(exposure_data.nbytes))
        self.logger.debug("Got exposure data from camera {}".format(camera_ID))
        return exposure_data

    def start_video_capture(self, camera_ID):
        """ Start video capture mode on camera with given integer ID """
        self._call_function('ASIStartVideoCapture', camera_ID)

    def stop_video_capture(self, camera_ID):
        """ Stop video capture mode on camera with given integer ID """
        self._call_function('ASIStopVideoCapture', camera_ID)

    def get_video_data(self, camera_ID, width, height, image_type, timeout):
        """ Get the image data from the next available video frame """
        video_data = self._image_array(width, height, image_type)
        timeout = int(get_quantity_value(timeout, unit=u.ms))
        try:
            self._call_function('ASIGetVideoData',
                                camera_ID,
                                video_data.ctypes.data_as(ctypes.POINTER(ctypes.c_byte)),
                                ctypes.c_long(video_data.nbytes),
                                ctypes.c_int(-1))
            # If set timeout to anything but -1 (no timeout) this call times out instantly?
        except RuntimeError:
            # Expect some dropped frames during video capture
            return None
        else:
            return video_data

    # Private methods

    def _call_function(self, function_name, camera_ID, *args):
        """ Utility function for calling the SDK functions that return ErrorCode """
        function = getattr(self._CDLL, function_name)
        error_code = function(ctypes.c_int(camera_ID), *args)
        if error_code != ErrorCode.SUCCESS:
            msg = "Error calling {}: {}".format(function_name, ErrorCode(error_code).name)
            self.logger.error(msg)
            raise RuntimeError(msg)

    def _parse_info(self, camera_info):
        """ Utility function to parse CameraInfo Structures into something more Pythonic """
        pythonic_info = {'name': camera_info.name.decode(),
                         'camera_ID': int(camera_info.camera_ID),
                         'max_height': camera_info.max_height * u.pixel,
                         'max_width': camera_info.max_width * u.pixel,
                         'is_color_camera': bool(camera_info.is_color_camera),
                         'bayer_pattern': BayerPattern(camera_info.bayer_pattern).name,
                         'supported_bins': self._parse_bins(camera_info.supported_bins),
                         'supported_video_format': self._parse_formats(
                             camera_info.supported_video_format),
                         'pixel_size': camera_info.pixel_size * u.um,
                         'has_mechanical_shutter': bool(camera_info.has_mechanical_shutter),
                         'has_ST4_port': bool(camera_info.has_ST4_port),
                         'has_cooler': bool(camera_info.has_cooler),
                         'is_USB3_host': bool(camera_info.is_USB3_host),
                         'is_USB3_camera': bool(camera_info.is_USB3_camera),
                         'e_per_adu': camera_info.e_per_adu * u.electron / u.adu,
                         'bit_depth': camera_info.bit_depth * u.bit,
                         'is_trigger_camera': bool(camera_info.is_trigger_camera)}
        return pythonic_info

    def _parse_bins(self, supported_bins):
        bins = tuple(int(b) for b in supported_bins if b != 0)
        return bins

    def _parse_formats(self, supported_formats):
        formats = []
        for supported_format in supported_formats:
            format = ImgType(supported_format)
            if format != ImgType.END:
                formats.append(format.name)
            else:
                break
        return tuple(formats)

    def _parse_caps(self, control_caps):
        """ Utility function to parse ControlCaps Structures into something more Pythonic """
        control_type = ControlType(control_caps.control_type).name
        control_info = {'name': control_caps.name.decode(),
                        'description': control_caps.description.decode(),
                        'max_value': self._parse_return_value(control_caps.max_value,
                                                              control_type),
                        'min_value': self._parse_return_value(control_caps.min_value,
                                                              control_type),
                        'default_value': self._parse_return_value(control_caps.default_value,
                                                                  control_type),
                        'is_auto_supported': bool(control_caps.is_auto_supported),
                        'is_writable': bool(control_caps.is_writable),
                        'control_type': control_type}
        return control_info

    def _parse_return_value(self, value, control_type):
        """ Helper function to apply appropiate type conversion and/or units to value """
        try:
            int_value = value.value  # If not done already extract Python int from ctypes.c_long
        except AttributeError:
            int_value = value  # If from a ctypes struct value will already be a Python int

        # Apply control type specific units and/or data types
        if control_type in units_and_scale:
            nice_value = int_value * units_and_scale[control_type]
        elif control_type in boolean_controls:
            nice_value = bool(int_value)
        elif control_type == 'FLIP':
            nice_value = FlipStatus(int_value).name
        else:
            nice_value = int_value

        return nice_value

    def _parse_input_value(self, value, control_type):
        """ Helper function to convert input values to appropriate ctypes.c_long """

        if control_type in units_and_scale:
            value = get_quantity_value(value, unit=units_and_scale[control_type])
        elif control_type == 'FLIP':
            value = FlipStatus[value]

        return ctypes.c_long(int(value))

    def _image_array(self, width, height, image_type):
        """ Creates a suitable numpy array for storing image data """
        width = int(get_quantity_value(width, unit=u.pixel))
        height = int(get_quantity_value(height, unit=u.pixel))

        if image_type in ('RAW8', 'Y8'):
            image_array = np.zeros((height, width), dtype=np.uint8, order='C')
        elif image_type == 'RAW16':
            image_array = np.zeros((height, width), dtype=np.uint16, order='C')
        elif image_type == 'RGB24':
            image_array = np.zeros((3, height, width), dtype=np.uint8, order='C')

        return image_array


units_and_scale = {'AUTO_TARGET_BRIGHTNESS': u.adu,
                   'AUTO_MAX_EXP': 1e-6 * u.second,  # Unit is microseconds
                   'BANDWIDTHOVERLOAD': u.percent,
                   'COOLER_POWER_PERC': u.percent,
                   'EXPOSURE': 1e-6 * u.second,  # Unit is microseconds
                   'OFFSET': u.adu,
                   'TARGET_TEMP': u.Celsius,
                   'TEMPERATURE': 0.1 * u.Celsius}  # Unit is 1/10th degree C

boolean_controls = ('ANTI_DEW_HEATER',
                    'COOLER_ON',
                    'FAN_ON',
                    'HARDWARE_BIN',
                    'HIGH_SPEED_MODE',
                    'MONO_BIN',
                    'PATTERN_ADJUST')

####################################################################################################
#
# The C defines, enums and structs from ASICamera2.h translated to Python constants, enums and
# ctypes.Structures. Based on v1.13.0930 of the ZWO ASI SDK.
#
####################################################################################################


ID_MAX = 128  # Maximum value for camera integer ID (camera_ID)


@enum.unique
class BayerPattern(enum.IntEnum):
    """ Bayer filter type """
    RG = 0
    BG = enum.auto()
    GR = enum.auto()
    GB = enum.auto()


@enum.unique
class ImgType(enum.IntEnum):
    """ Supported video format """
    RAW8 = 0
    RGB24 = enum.auto()
    RAW16 = enum.auto()
    Y8 = enum.auto()
    END = -1


@enum.unique
class GuideDirection(enum.IntEnum):
    """ Guider direction """
    NORTH = 0
    SOUTH = enum.auto()
    EAST = enum.auto()
    WEST = enum.auto()


@enum.unique
class FlipStatus(enum.IntEnum):
    """ Flip status """
    NONE = 0
    HORIZ = enum.auto()
    VERT = enum.auto()
    BOTH = enum.auto()


@enum.unique
class CameraMode(enum.IntEnum):
    """ Camera status """
    NORMAL = 0
    TRIG_SOFT_EDGE = enum.auto()
    TRIG_RISE_EDGE = enum.auto()
    TRIG_FALL_EDGE = enum.auto()
    TRIG_SOFT_LEVEL = enum.auto()
    TRIG_HIGH_LEVEL = enum.auto()
    TRIG_LOW_LEVEL = enum.auto()
    END = -1


@enum.unique
class TrigOutput(enum.IntEnum):
    """External trigger output."""

    PINA = 0  # Only Pin A output
    PINB = enum.auto()  # Only Pin B outoput
    NONE = -1


@enum.unique
class ErrorCode(enum.IntEnum):
    """ Error codes """
    SUCCESS = 0
    INVALID_INDEX = enum.auto()  # No camera connected or index value out of boundary
    INVALID_ID = enum.auto()
    INVALID_CONTROL_TYPE = enum.auto()
    CAMERA_CLOSED = enum.auto()  # Camera didn't open
    CAMERA_REMOVED = enum.auto()  # Failed to fine the camera, maybe it was removed
    INVALID_PATH = enum.auto()  # Cannot find the path of the file
    INVALID_FILEFORMAT = enum.auto()
    INVALID_SIZE = enum.auto()  # Wrong video format size
    INVALID_IMGTYPE = enum.auto()  # Unsupported image format
    OUTOF_BOUNDARY = enum.auto()  # The startpos is out of boundary
    TIMEOUT = enum.auto()
    INVALID_SEQUENCE = enum.auto()  # Stop capture first
    BUFFER_TOO_SMALL = enum.auto()
    VIDEO_MODE_ACTIVE = enum.auto()
    EXPOSURE_IN_PROGRESS = enum.auto()
    GENERAL_ERROR = enum.auto()  # General error, e.g. value is out of valid range
    INVALID_MODE = enum.auto()  # The current mode is wrong
    END = enum.auto()


class CameraInfo(ctypes.Structure):
    """ Camera info structure """
    _fields_ = [('name', ctypes.c_char * 64),
                ('camera_ID', ctypes.c_int),
                ('max_height', ctypes.c_long),
                ('max_width', ctypes.c_long),
                ('is_color_camera', ctypes.c_int),
                ('bayer_pattern', ctypes.c_int),
                ('supported_bins', ctypes.c_int * 16),  # e.g. (1,2,4,8,0,...) means 1x, 2x, 4x, 8x
                ('supported_video_format', ctypes.c_int * 8),  # ImgTypes, terminates with END
                ('pixel_size', ctypes.c_double),  # in microns
                ('has_mechanical_shutter', ctypes.c_int),
                ('has_ST4_port', ctypes.c_int),
                ('has_cooler', ctypes.c_int),
                ('is_USB3_host', ctypes.c_int),
                ('is_USB3_camera', ctypes.c_int),
                ('e_per_adu', ctypes.c_float),
                ('bit_depth', ctypes.c_int),
                ('is_trigger_camera', ctypes.c_int),
                ('unused', ctypes.c_char * 16)]


class ControlType(enum.IntEnum):
    """ Control types """
    GAIN = 0
    EXPOSURE = enum.auto()
    GAMMA = enum.auto()
    WB_R = enum.auto()
    WB_B = enum.auto()
    OFFSET = enum.auto()
    BANDWIDTHOVERLOAD = enum.auto()
    OVERCLOCK = enum.auto()
    TEMPERATURE = enum.auto()  # Returns temperature*10
    FLIP = enum.auto()
    AUTO_MAX_GAIN = enum.auto()
    AUTO_MAX_EXP = enum.auto()  # in microseconds
    AUTO_TARGET_BRIGHTNESS = enum.auto()
    HARDWARE_BIN = enum.auto()
    HIGH_SPEED_MODE = enum.auto()
    COOLER_POWER_PERC = enum.auto()
    TARGET_TEMP = enum.auto()  # NOT *10
    COOLER_ON = enum.auto()
    MONO_BIN = enum.auto()  # Leads to less grid at software bin mode for colour camera
    FAN_ON = enum.auto()
    PATTERN_ADJUST = enum.auto()
    ANTI_DEW_HEATER = enum.auto()

    BRIGHTNESS = OFFSET
    AUTO_MAX_BRIGHTNESS = AUTO_TARGET_BRIGHTNESS


class ControlCaps(ctypes.Structure):
    """ Structure for caps (limits) on allowable parameter values for each camera control """
    _fields_ = [('name', ctypes.c_char * 64),  # The name of the control, .e.g. Exposure, Gain
                ('description', ctypes.c_char * 128),  # Description of the command
                ('max_value', ctypes.c_long),
                ('min_value', ctypes.c_long),
                ('default_value', ctypes.c_long),
                ('is_auto_supported', ctypes.c_int),
                ('is_writable', ctypes.c_int),  # Some can be read only, e.g. temperature
                ('control_type', ctypes.c_int),  # ControlType used to get/set value
                ('unused', ctypes.c_char * 32)]


class ExposureStatus(enum.IntEnum):
    """ Exposure status codes """
    IDLE = 0
    WORKING = enum.auto()
    SUCCESS = enum.auto()
    FAILED = enum.auto()


class ID(ctypes.Structure):
    _fields_ = [('id', ctypes.c_ubyte * 8)]


class SupportedMode(ctypes.Structure):
    """ Array of supported CameraModes, terminated with CameraMode.END """
    _fields_ = [('modes', ctypes.c_int * 16)]
