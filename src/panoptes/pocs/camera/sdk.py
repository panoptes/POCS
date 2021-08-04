import time
from abc import ABCMeta, abstractmethod
from contextlib import suppress

from panoptes.pocs.base import PanBase
from panoptes.pocs.camera.camera import AbstractCamera
from panoptes.utils import error
from panoptes.utils.library import load_c_library
from panoptes.pocs.utils.logger import get_logger

# Would usually use self.logger but that won't exist until after calling super().__init__(),
# and don't want to do that until after the serial number and port have both been determined
# in order to avoid log entries with misleading values. To enable logging during the device
# scanning phase use get_logger() instead.
# TODO figure out how to remove this.
logger = get_logger()


class AbstractSDKDriver(PanBase, metaclass=ABCMeta):
    def __init__(self, name, library_path=None, *args, **kwargs):
        """Base class for all camera SDK interfaces.

        On construction loads the shared object/dynamically linked version of the camera SDK
        library, which must be already installed.

        The name and location of the shared library can be manually specified with the library_path
        argument, otherwise the ctypes.util.find_library function will be used to try to locate it.

        Args:
            name (str): name of the library (without 'lib' prefix or any suffixes, e.g. 'fli').
            library_path (str, optional): path to the libary e.g. '/usr/local/lib/libASICamera2.so'

        Raises:
            panoptes.utils.error.NotFound: raised if library_path not given & find_libary fails to
                locate the library.
            OSError: raises if the ctypes.CDLL loader cannot load the library.
        """
        # Most SDK cameras can take internal darks so set to True by default.
        kwargs['internal_darks'] = kwargs.get('internal_darks', True)
        super().__init__(**kwargs)
        self._CDLL = load_c_library(name=name, path=library_path)
        self._version = self.get_SDK_version()
        self.logger.debug("{} driver ({}) initialised.".format(name, self._version))

    # Properties

    @property
    def version(self):
        return self._version

    # Methods

    @abstractmethod
    def get_SDK_version(self):
        """ Get the version of the SDK """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def get_devices(self):
        """Get connected device UIDs and corresponding device nodes/handles/IDs."""
        raise NotImplementedError  # pragma: no cover


class AbstractSDKCamera(AbstractCamera):
    _driver = None
    _cameras = dict()
    _assigned_cameras = set()

    def __init__(self,
                 name='Generic SDK camera',
                 driver=AbstractSDKDriver,
                 library_path=None,
                 filter_type=None,
                 target_temperature=None,
                 *args, **kwargs):

        # The SDK cameras don't generally have a 'port', they are identified by a serial_number,
        # which is some form of unique ID readable via the camera SDK.
        kwargs['port'] = None
        serial_number = kwargs.get('serial_number')
        if not serial_number:
            msg = f"Must specify serial_number for {name}."
            logger.error(msg)
            raise ValueError(msg)

        # Get class of current object in a way that works in derived classes
        my_class = type(self)

        if my_class._driver is None:
            # Initialise the driver if it hasn't already been done
            my_class._driver = driver(library_path=library_path)

        logger.debug(f"Looking for name={name!r} with UID 'serial_number={serial_number!r}'.")

        if not my_class._cameras:
            # No cached camera details, need to probe for connected cameras
            # This will raise a PanError if there are no cameras.
            my_class._cameras = my_class._driver.get_devices()

        logger.debug(f"Connected {name} devices: {my_class._cameras}")

        if serial_number in my_class._cameras:
            logger.debug(f"Found {name} with UID serial_number={serial_number!r} at {my_class._cameras[serial_number]}.")
        else:
            raise error.InvalidConfig(f"No config information found for "
                                      f"name={name!r} with serial_number={serial_number!r} in {my_class._cameras}")

        if serial_number in my_class._assigned_cameras:
            raise error.PanError(f"{name} with UID serial_number={serial_number!r} already in use.")
        else:
            my_class._assigned_cameras.add(serial_number)

        self._info = dict()
        super().__init__(name, *args, **kwargs)
        self._address = my_class._cameras[self.uid]
        self.connect()
        if not self.is_connected:
            raise error.PanError(f"Could not connect to {self}.")

        if filter_type:
            # connect() will have set this based on camera info, but that doesn't know about filters
            # upstream of the CCD. Can be set manually here, or handled by a filterwheel attribute.
            self._filter_type = filter_type

        if target_temperature is not None:
            if self.is_cooled_camera:
                self.target_temperature = target_temperature

                # Setting this will call _check_temperature_stability
                self.cooling_enabled = True

                # Block here while camera temperature stabilises
                while self.is_temperature_stable is False:
                    time.sleep(0.5)

                msg = f"Set target temperature {target_temperature} & enabled cooling on {self}."
                self.logger.debug(msg)
            else:
                msg = "Setting a target temperature on uncooled camera {}".format(self)
                self.logger.warning(msg)

    def __del__(self):
        """ Attempt some clean up. """
        if hasattr(self, 'uid'):
            logger.trace(f'Removing {self.uid} from: {type(self)._assigned_cameras}')
            type(self)._assigned_cameras.discard(self.uid)

        logger.trace(f'Assigned cameras after removing: {type(self)._assigned_cameras}')

    # Properties

    @property
    def properties(self):
        """ A collection of camera properties as read from the camera """
        return self._info

    # Methods

    def _create_fits_header(self, seconds, dark=None):
        header = super()._create_fits_header(seconds, dark=dark)
        header.set('CAM-SDK', type(self)._driver.version, 'Camera SDK version')
        return header

    def __str__(self):
        # SDK cameras don't have a port so just include the serial number in the string
        # representation.
        s = f"{self.name} ({self.uid})"

        with suppress(AttributeError):
            if self.focuser:
                s += f' with {self.focuser.name}'
                if self.filterwheel:
                    s += f' & {self.filterwheel.name}'

        with suppress(AttributeError):
            if self.filterwheel:
                s += f' with {self.filterwheel.name}'

        return s
