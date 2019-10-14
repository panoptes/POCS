import ctypes
import enum

from pocs.camera.sdk import AbstractSDKDriver
from pocs.utils import error
from pocs.utils.library import load_library


class EFWDriver(AbstractSDKDriver):
    # Because ZWO EFW library isn't linked properly have to manually load libudev
    # in global mode first, otherwise get undefined symbol errors.
    _libudev = load_library('udev', mode=ctypes.RTLD_GLOBAL)

    def __init__(self, library_path=None, **kwargs):
        """Main class representing the ZWO EFW library interface.

        On construction loads the shared object/dynamically linked version of the EFW SDK library,
        which must be already installed (see https://astronomy-imaging-camera.com/software-drivers).

        The name and location of the shared library can be manually specified with the library_path
        argument, otherwise the ctypes.util.find_library function will be used to try to locate it.

        Args:
            library_path (str, optional): path to the libary e.g. '/usr/local/lib/libEFWFilter.so'

        Returns:
            `~pocs.filter.libefw.EFWDriver`

        Raises:
            pocs.utils.error.NotFound: raised if library_path not given & find_library fails to
                locate the library.
            OSError: raises if the ctypes.CDLL loader cannot load the library.
        """
        super().__init__(name='EFWFilter', library_path=library_path, **kwargs)

    # Methods

    def get_SDK_version(self):
        """Get the version for the SDK."""
        return "Unknown"

    def get_devices(self):
        """Convenience function to get a dictionary of all currently connected device UIDs
        and their corresponding device nodes/handles/IDs.
        """
        return {}

    def get_num_of_connected_filterwheels(self):
        """Get teh count of connected EFW filterwheels."""
        count = self._CDLL.EFWGetNum()
        self.logger.debug(f"Found {count} connected EFW filterwheels.")
        return count

    # Private methods

    def _call_function(self, function_name, filterwheel_ID, *args):
        """Utility function for calling the SDK functions that return ErrorCode."""
        function = getattr(self._CDLL, function_name)
        error_code = function(ctypes.c_int(filterwheel_ID), *args)
        if error_code != ErrorCode.SUCCESS:
            msg = "Error calling {}: {}".format(function_name, ErrorCode(error_code).name)
            self.logger.error(msg)
            raise error.PanError(msg)


class EFWInfo(ctypes.Structure):
    """Filterwheel info structure."""

    _fields_ = [('filterwheel_ID', ctypes.c_int),
                ('name', ctypes.c_char * 64),
                ('slot_num', ctypes.c_int)]


@enum.unique
class ErrorCode(enum.IntEnum):
    SUCCESS = 0
    INVALID_INDEX = enum.auto()
    INVALID_ID = enum.auto()
    INVALID_VALUE = enum.auto()
    REMOVED = enum.auto()  # failed to find the filter wheel, maybe it has been removed
    MOVING = enum.auto()  # filter wheel is moving
    ERROR_STATE = enum.auto()  # filter wheel is in error state
    GENERAL_ERROR = enum.auto()  # other error
    NOT_SUPPORTED = enum.auto()
    CLOSED = enum.auto()
    END = -1
