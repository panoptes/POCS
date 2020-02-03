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
        # EFW SDK has no way to access SDK version.
        return "Unknown"

    def get_devices(self):
        """Get connected device UIDs and corresponding device nodes/handles/IDs.
        """
        # EFW SDK has no way to access any unique identifier for connected filterwheels.
        # Construct an ID (probably not deterministic, in general) from combination of
        # product code and filterwheel ID.
        n_filterwheels = self.get_num()  # Nothing works if you don't call this first.
        products = self.get_product_ids()  # Will raise error.NotFound if no filterwheels
        ids = [self.get_ID(i) for i in range(n_filterwheels)]
        filterwheels = {f"{product}_{id}": id for product, id in zip(products, ids)}
        return filterwheels

    def get_num(self):
        """Get the count of connected EFW filterwheels."""
        count = self._CDLL.EFWGetNum()
        self.logger.debug(f"Found {count} connected EFW filterwheels.")
        return count

    def get_product_ids(self):
        """Get product IDs of connected EFW filterwheels."""
        n_filterwheels = self._CDLL.EFWGetProductIDs(0)
        if n_filterwheels > 0:
            product_ids = (ctypes.c_int * n_filterwheels)()
            assert n_filterwheels == self._CDLL.EFWGetProductIDs(ctypes.byref(product_ids))
        else:
            raise error.NotFound("No connected EFW filterwheels.")
        self.logger.debug(f"Got product IDs from {n_filterwheels} filterwheels.")
        return list(product_ids)

    def get_ID(self, filterwheel_index):
        """Get integer ID of filterwheel with a given index."""
        filterwheel_ID = ctypes.c_int()
        self._call_function('EFWGetID',
                            filterwheel_index,
                            ctypes.byref(filterwheel_ID))
        self.logger.debug(f"Got filterwheel ID {filterwheel_ID} for index {filterwheel_index}.")
        return filterwheel_ID.value

    def open(self, filterwheel_ID):
        """Open connection to filterwheel with given ID."""
        self._call_function('EFWOpen',
                            filterwheel_ID)
        self.logger.debug(f"Connection to filterwheel {filterwheel_ID} opened.")

    def get_property(self, filterwheel_ID):
        """Get properties of filterwheel with given ID."""
        filterwheel_info = EFWInfo()
        self._call_function('EFWGetProperty',
                            filterwheel_ID,
                            ctypes.byref(filterwheel_info))
        filterwheel_properties = self._parse_info(filterwheel_info)
        self.logger.debug(f"Got properties from filterweel {filterwheel_ID}.")
        return filterwheel_properties

    def get_position(self, filterwheel_ID):
        """Get current position of filterwheel with given ID."""
        position = ctypes.c_int()
        self._call_function('EFWGetPosition',
                            filterwheel_ID,
                            ctypes.byref(position))
        self.logger.debug(f"Got position {position} from filterwheel {filterwheel_ID}.")
        return position.value

    def set_position(self, filterwheel_ID, position):
        """Set position of filterwheel with given ID."""
        self._call_function('EFWSetPosition',
                            filterwheel_ID,
                            ctypes.c_int(position))
        self.logger.debug(f"Setting position {position} on filterwheel {filterwheel_ID}.")

    def get_direction(self, filterwheel_ID):
        """Get current unidirectional/bidirectional setting of filterwheel with given ID."""
        unidirectional = ctypes.c_bool()
        self._call_function('EFWGetDirection',
                            filterwheel_ID,
                            ctypes.byref(unidirectional))
        unidirectional = bool(unidirectional)
        self.logger.debug(f"Got unidirectional={unidirectional} from filterwheel {filterwheel_ID}.")
        return unidirectional.value

    def set_direction(self, filterwheel_ID, unidirectional):
        """Set unidrectional/bidirectional for filterwheel with given ID."""
        self._call_function('EFWSetDirection',
                            filterwheel_ID,
                            ctypes.c_bool(unidirectional))
        self.logger.debug(f"Set unidirection={unidirectional} for filterwheel {filterwheel_ID}.")

    def calibrate(self, filterwheel_ID):
        """Calibrate filterwheel with given ID."""
        self._call_function('EFWCalibrate',
                            filterwheel_ID)
        self.logger.debug(f"Calibrating filterwheel {filterwheel_ID}.")

    def close(self, filterwheel_ID):
        """Close connection to filterwheel with given ID."""
        self._call_function('EFWClose',
                            filterwheel_ID)
        self.logger.debug(f"Connection to filterwheel {filterwheel_ID} closed.")

    # Private methods

    def _call_function(self, function_name, filterwheel_ID, *args):
        """Utility function for calling the SDK functions that return ErrorCode."""
        function = getattr(self._CDLL, function_name)
        error_code = function(ctypes.c_int(filterwheel_ID), *args)
        if error_code != ErrorCode.SUCCESS:
            msg = "Error calling {}: {}".format(function_name, ErrorCode(error_code).name)
            self.logger.error(msg)
            raise error.PanError(msg)

    def _parse_info(self, filterwheel_info):
        """Convert EFWInfo ctypes.Structure into a Pythonic dict."""
        properties = {'id': filterwheel_info.id,
                      'name': filterwheel_info.name.decode(),
                      'slot_num': filterwheel_info.slot_num}
        return properties


class EFWInfo(ctypes.Structure):
    """Filterwheel info structure."""

    _fields_ = [('id', ctypes.c_int),
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
