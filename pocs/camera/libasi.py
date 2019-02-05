import ctypes
import enum

from astropy import units as u

from pocs.base import PanBase
from pocs.utils import error
from pocs.utils.library import load_library

####################################################################################################
#
# Main ASI Driver class.
#
# The methods of this class call the functions fron ASICamera2.h using the ctypes foreign function
# library. Based on v1.13.0930 of the ZWO ASI SDK.
#
####################################################################################################


class ASIDriver(PanBase):
    def __init__(self, library_path=None, *args, **kwargs):
        """Main class representing the ZWO ASI library interface. On construction loads the shared
        object/dynamically linked version of the ASI SDK library, which must be already installed
        (see https://astronomy-imaging-camera.com/software-drivers).

        The name and location of the shared library can be manually specified with the library_path
        argument, otherwise the ctypes.util.find_library function will be used to try to locate it.

        Args:
            library_path (str, optional): path to the libary e.g. '/usr/local/lib/libASICamera2.so'

        Returns:
            `~pocs.camera.libasi.ASIDriver`

        Raises:
            pocs.utils.error.NotFound: raised if library_path not given & find_libary fails to
                locate the library.
            OSError: raises if the ctypes.CDLL loader cannot load the library.
        """
        super().__init__(*args, **kwargs)
        library = load_library(name='ASICamera2', path=library_path, logger=self.logger)
        self._CDLL = library
        self._version = self.get_SDK_version()

    # Properties

    @property
    def version(self):
        """ Version of the ZWO ASI SDK """
        return self._version

    # Methods

    def get_num_of_connected_cameras(self):
        """ Get the count of connected ASI cameras """
        count = self._CDLL.ASIGetNumOfConnectedCameras()  # Return type is int, needs no Pythonising
        self.logger.debug("Found {} connected ASI cameras".format(count))
        return count

    def get_SDK_version(self):
        """ Get the version of the ZWO ASI SDK """
        # First set return type for function to pointer to null terminated string
        self._CDLL.ASIGetSDKVersion.restype = ctypes.c_char_p
        version = self._CDLL.ASIGetSDKVersion().decode('ascii')  # Get bytes so decode to str
        version = version.replace(', ', '.')  # Format the version string properly
        self.logger.debug("ZWO ASI SDK version: {}".format(version))
        return version

    def get_camera_property(self, camera_index):
        """ Get properties of the camera with given index """
        camera_info = CameraInfo()
        error_code = self._CDLL.ASIGetCameraProperty(ctypes.byref(camera_info), camera_index)
        if error_code != ErrorCode.SUCCESS:
            msg = "Error calling ASIGetCameraProperty: {}".format(ErrorCode(error_code).name)
            self.logger.error(msg)
            raise RuntimeError(msg)

        pythonic_info = self._parse_info(camera_info)
        self.logger.debug("Got info from camera {}, {}".format(pythonic_info['camera_ID'],
                                                               pythonic_info['name']))
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
        self.logger.debug("Got string ID '{}'' from camera {}".format(string_ID, camera_ID))
        return string_ID

    def set_ID(self, camera_ID, string_ID):
        """Save string ID to firmware of camera with given integer ID

        The saved ID is an array of 8 unsigned chars for some reason. To preserve some sanity
        this method takes an 8 byte UTF-8 string as input.
        """
        bytes_ID = string_ID.encode()  # Convert string to bytes
        if len(bytes_ID) > 8:
            bytes_ID = bytes_ID[:8]
            self.logger.warning("New ID longer than 8 bytes, truncating {} to {}".format(
                string_ID, bytes_ID.decode()))
        else:
            bytes_ID = bytes_ID.ljust(8)  # Pad to 8 butes if necessary
        uchar_ID = (ctypes.c_ubyte * 8).from_buffer_copy(bytes_ID)
        self._call_function('ASISetID', camera_ID, ID(uchar_ID))
        self.logger.debug("Set camera {} string ID to '{}'".format(camera_ID, bytes_ID.decode()))

    # Private methods

    def _parse_info(self, camera_info):
        pythonic_info = {'name': camera_info.name.decode('ascii'),
                         'camera_ID': int(camera_info.camera_ID),
                         'max_height': camera_info.max_height * u.pixel,
                         'max_width': camera_info.max_width * u.pixel,
                         'is_colour_camera': bool(camera_info.is_color_camera),
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
        bins = tuple(int(bin) for bin in supported_bins if bin != 0)
        return bins

    def _parse_formats(self, supported_formats):
        formats = []
        for i in range(8):
            format = ImgType(supported_formats[i])
            if format != ImgType.END:
                formats.append(format.name)
            else:
                break
        return tuple(formats)

    def _call_function(self, function_name, camera_id, *args):
        """ Utility functions for calling the functions that take return ErrorCode """
        function = getattr(self._CDLL, function_name)
        error_code = function(ctypes.c_int(camera_id), *args)
        if error_code != ErrorCode.SUCCESS:
            msg = "Error calling {}: {}".format(function_name, ErrorCode(error_code).name)
            self.logger.error(msg)
            raise RuntimeError(msg)


####################################################################################################
#
# The C defines, enums and structs from ASICamera2.h translated to Python constants, enums and
# ctypes.Structures. Based on v1.13.0930 of the ZWO ASI SDK.
#
####################################################################################################


ID_MAX = 128


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
