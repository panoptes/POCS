import ctypes
import enum

####################################################################################################
#
# The C defines, enums and structs from ASICamera2.h translated to Python constants, enums and
# ctypes.Structures. Based on v1.13.0930 of the ZWO ASI SDK.
#
####################################################################################################

ID_MAX = 128


@enum.unique
class BayerPattern(IntEnum):
    """ Bayer filter type """
    RG = 0
    BG = enum.auto()
    GR = enum.auto()
    GB = enum.auto()


@enum.unique
class ImgType(IntEnum):
    """ Supported video format """
    RAW8 = 0
    RGB24 = enum.auto()
    RAW16 = enum.auto()
    Y8 = enum.auto()
    END = -1


@enum.unique
class GuideDirection(IntEnum):
    """ Guider direction """
    NORTH = 0
    SOUTH = enum.auto()
    EAST = enum.auto()
    WEST = enum.auto()


@enum.unique
class FlipStatus(IntEnum):
    """ Flip status """
    NONE = 0
    HORIZ = enum.auto()
    VERT = enum.auto()
    BOTH = enum.auto()


@enum.unique
class CameraMode(IntEnum):
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
class ErrorCode(IntEnum):
    """ Error codes """
    SUCCESS = 0
    INVALID_INDIEX = enum.auto()  # No camera connected or index value out of boundary
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
                ('is_color_camera', ctypes.c_bool),
                ('bayer_pattern', ctypes.c_ushort),
                ('supported_bins', ctypes.c_int * 16),  # e.g. (1,2,4,8,0,...) means 1x, 2x, 4x, 8x
                ('supported_video_format', ctypes.c_short * 8),  # ImgTypes, terminates with END
                ('pixel_size', ctypes.c_double),  # in microns
                ('has_mechanical_shutter', ctypes.c_bool),
                ('has_ST4_port', ctypes.c_bool),
                ('has_cooler', ctypes.c_bool),
                ('is_USB3_host', ctypes.c_bool),
                ('is_USB3_camera', ctypes.c_bool),
                ('e_per_adu', ctypes.c_float),
                ('bit_depth', ctypes.c_int),
                ('is_trigger_camera', ctypes.c_bool),
                ('unused', ctypes.c_char * 16)]


class ControlType(IntEnum):
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
    TARGET_TEMP  # NOT *10
    COOLER_ON = enum.auto()
    MONO_BIN = enum.auto()  # Leads to les grid at software bin mode for colour camera
    FAN_ON = enum.auto()
    PATTERN_ADJUST = enum.auto()
    ANTI_DEW_HEATER = enum.auto()

    BRIGHTNESS = OFFSET
    AUTO_MAX_BRIGHTNESS = TARGET_BRIGHTNESS


class ControlCaps(ctypes.Structure):
    """ Structure for caps (limits) on allowable parameter values for each camera control """
    _fields_ = [('name', ctypes.c_char * 64),  # The name of the control, .e.g. Exposure, Gain
                ('description', ctypes.c_char * 128),  # Description of the command
                ('max_value', ctypes.c_long),
                ('min_value', ctypes.c_long),
                ('default_value', ctypes.c_long),
                ('is_auto_supported', ctypes.c_bool),
                ('is_writable', ctypes.c_bool),  # Some can be read only, e.g. temperature
                ('control_type', ctypes.c_ushort),  # ControlType used to get/set value
                ('unused', ctypes.c_char * 32)]
