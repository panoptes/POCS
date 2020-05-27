import ctypes
import enum
import threading
import time

from panoptes.pocs.camera.sdk import AbstractSDKDriver
from panoptes.utils import error
from panoptes.utils.library import load_c_library
from panoptes.utils import CountdownTimer


class EFWDriver(AbstractSDKDriver):
    # Because ZWO EFW library isn't linked properly have to manually load libudev
    # in global mode first, otherwise get undefined symbol errors.
    _libudev = load_c_library('udev', mode=ctypes.RTLD_GLOBAL)

    def __init__(self, library_path=None, **kwargs):
        """Main class representing the ZWO EFW library interface.

        On construction loads the shared object/dynamically linked version of the EFW SDK library,
        which must be already installed (see https://astronomy-imaging-camera.com/software-drivers).

        The name and location of the shared library can be manually specified with the library_path
        argument, otherwise the ctypes.util.find_library function will be used to try to locate it.

        Args:
            library_path (str, optional): path to the library e.g. '/usr/local/lib/libEFWFilter.so'

        Returns:
            `~pocs.filter.libefw.EFWDriver`

        Raises:
            `panoptes.utils.error.NotFound`: raised if library_path not given & find_library fails to
                locate the library.
            `OSError`: raises if the ctypes.CDLL loader cannot load the library.
        """
        super().__init__(name='EFWFilter', library_path=library_path, **kwargs)

    # Methods

    def get_SDK_version(self):
        """Get the version for the SDK."""
        # EFW SDK has no way to access SDK version.
        return "Unknown"

    def get_devices(self):
        """Get connected device 'UIDs' and corresponding device nodes/handles/IDs.

        EFW SDK has no way to access any unique identifier for connected filterwheels.
        Instead we construct an ID from combination of filterwheel name, number of
        positions and integer ID. This will probably not be deterministic, in general,
        and is only guaranteed to be unique between multiple filterwheels on a single
        computer.
        """
        n_filterwheels = self.get_num()  # Nothing works if you don't call this first.
        if n_filterwheels < 1:
            raise error.NotFound("No ZWO EFW filterwheels found.")

        filterwheels = {}
        for i in range(n_filterwheels):
            fw_id = self.get_ID(i)
            try:
                self.open(fw_id)
            except error.PanError as err:
                self.logger.error(f"Error opening filterwheel {fw_id}. {err!r}")
            else:
                info = self.get_property(fw_id)
                filterwheels[f"{info['name']}_{info['slot_num']}_{fw_id}"] = fw_id
            finally:
                self.close(fw_id)
        if not filterwheels:
            self.logger.warning("Could not get properties of any EFW filterwheels.")

        return filterwheels

    def get_num(self):
        """Get the count of connected EFW filterwheels."""
        count = self._CDLL.EFWGetNum()
        self.logger.debug(f"Found {count} connected EFW filterwheels.")
        return count

    def get_product_ids(self):
        """Get product IDs of supported(?) EFW filterwheels.

        The SDK documentation does not explain what the product IDs returned by this function are,
        but from experiment and analogy with a similar function in the ASI camera SDK it appears
        this is a list of the product IDs of the filterwheels that the SDK supports, not the
        product IDs of the connected filterwheels. There appears to be no way to obtain the
        product IDs of the connected filterwheel(s).
        """
        n_filterwheels = self._CDLL.EFWGetProductIDs(0)
        if n_filterwheels > 0:
            product_ids = (ctypes.c_int * n_filterwheels)()
            assert n_filterwheels == self._CDLL.EFWGetProductIDs(ctypes.byref(product_ids))
        else:
            raise error.NotFound("No connected EFW filterwheels.")
        product_ids = list(product_ids)
        self.logger.debug(f"Got supported product IDs: {product_ids}")
        return product_ids

    def get_ID(self, filterwheel_index):
        """Get integer ID of filterwheel with a given index."""
        filterwheel_ID = ctypes.c_int()
        self._call_function('EFWGetID',
                            filterwheel_index,
                            ctypes.byref(filterwheel_ID))
        filterwheel_ID = filterwheel_ID.value
        self.logger.debug(f"Got filterwheel ID {filterwheel_ID} for index {filterwheel_index}.")
        return filterwheel_ID

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
        self.logger.debug(f"Got properties from filterwheel {filterwheel_ID}.")
        return filterwheel_properties

    def get_position(self, filterwheel_ID):
        """Get current position of filterwheel with given ID."""
        position = ctypes.c_int()
        self._call_function('EFWGetPosition',
                            filterwheel_ID,
                            ctypes.byref(position))
        return position.value

    def set_position(self, filterwheel_ID, position, move_event=None, timeout=None):
        """Set position of filterwheel with given ID.

        This function returns immediately after starting the move but spawns a thread to poll the
        filter wheel until the move completes (see _efw_poll method for details). This thread will
        log the result of the move, and optionally set a threading.Event to signal that it has
        completed.

        Args:
            filterwheel_ID (int): integer ID of the filterwheel that is moving.
            position (int): position to move the filter wheel. Must an integer >= 0.
            move_event (threading.Event, optional): Event to set once the move is complete
            timeout (u.Quantity, optional): maximum time to wait for the move to complete. Should be
                a Quantity with time units. If a numeric type without units is given seconds will be
                assumed.

        Raises:
            `panoptes.utils.error.PanError`: raised if the driver returns an error starting the move.
        """
        self.logger.debug(f"Setting position {position} on filterwheel {filterwheel_ID}.")
        # This will raise errors if the filterwheel is already moving, or position is not valid.
        self._call_function('EFWSetPosition',
                            filterwheel_ID,
                            ctypes.c_int(position))
        poll_thread = threading.Thread(target=self._efw_poll,
                                       args=(filterwheel_ID, position, move_event, timeout),
                                       daemon=True)
        poll_thread.start()

    def get_direction(self, filterwheel_ID):
        """Get current unidirectional/bidirectional setting of filterwheel with given ID."""
        unidirectional = ctypes.c_bool()
        self._call_function('EFWGetDirection',
                            filterwheel_ID,
                            ctypes.byref(unidirectional))
        unidirectional = unidirectional.value
        self.logger.debug(f"Got unidirectional={unidirectional} from filterwheel {filterwheel_ID}.")
        return unidirectional

    def set_direction(self, filterwheel_ID, unidirectional):
        """Set unidrectional/bidirectional for filterwheel with given ID."""
        self._call_function('EFWSetDirection',
                            filterwheel_ID,
                            ctypes.c_bool(unidirectional))
        self.logger.debug(f"Set unidirectional={unidirectional} for filterwheel {filterwheel_ID}.")

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

    def _efw_poll(self, filterwheel_ID, position, move_event, timeout):
        """
        Polls filter wheel until the current move is complete.

        Also monitors for errors while polling and checks position after the move is complete.
        Optionally sets a threading.Event to signal the end of the move. Has an optional timeout
        to raise an TimeoutError is the move takes longer than expected.

        Args:
            filterwheel_ID (int): integer ID of the filterwheel that is moving.
            position (int): position to move the filter wheel. Must be an integer >= 0.
            move_event (threading.Event, optional): Event to set once the move is complete
            timeout (u.Quantity, optional): maximum time to wait for the move to complete. Should
                be a Quantity with time units. If a numeric type without units is given seconds
                will be assumed.

            Raises:
                `panoptes.utils.error.PanError`: raised if the driver returns an error or if the final
                    position is not as expected.
                `panoptes.utils.error.Timeout`: raised if the move does not end within the period of
                    time specified by the timeout argument.
        """
        if timeout is not None:
            timer = CountdownTimer(duration=timeout)

        try:
            # No status query function in the SDK. Only way to check on progress of move
            # is to keep issuing the same move command until we stop getting the MOVING
            # error code back.
            error_code = self._CDLL.EFWSetPosition(ctypes.c_int(filterwheel_ID),
                                                   ctypes.c_int(position))
            while error_code == ErrorCode.MOVING:
                if timeout is not None and timer.expired():
                    msg = "Timeout waiting for filterwheel {} to move to {}".format(
                        filterwheel_ID, position)
                    raise error.Timeout(msg)
                time.sleep(0.1)
                error_code = self._CDLL.EFWSetPosition(ctypes.c_int(filterwheel_ID),
                                                       ctypes.c_int(position))

            if error_code != ErrorCode.SUCCESS:
                # Got some sort of error while polling.
                msg = "Error while moving filterwheel {} to {}: {}".format(
                    filterwheel_ID, position, ErrorCode(error_code).name)
                self.logger.error(msg)
                raise error.PanError(msg)

            final_position = self.get_position(filterwheel_ID)
            if final_position != position:
                msg = "Tried to move filterwheel {} to {}, but ended up at {}.".format(
                    filterwheel_ID, position, final_position)
                self.logger.error(msg)
                raise error.PanError(msg)

            self.logger.debug(f"Filter wheel {filterwheel_ID} moved to {position}.")
        finally:
            # Regardless must always set the Event when the move has stopped.
            if move_event is not None:
                move_event.set()

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
