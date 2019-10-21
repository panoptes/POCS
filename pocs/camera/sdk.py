from abc import ABCMeta, abstractmethod
from contextlib import suppress

from pocs.base import PanBase
from pocs.camera.camera import AbstractCamera
from panoptes.utils import error
from panoptes.utils.library import load_c_library
from panoptes.utils.logger import get_root_logger


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
        print(f'Creating AbstractSDKDriver camera: {kwargs!r}')

        super().__init__(*args, **kwargs)
        self._CDLL = load_c_library(name=name, path=library_path, logger=self.logger)
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
    def get_cameras(self):
        """Convenience function to get a dictionary of all currently connected camera UIDs
        and their corresponding device nodes/handles/camera IDs.
        """
        raise NotImplementedError  # pragma: no cover


class AbstractSDKCamera(AbstractCamera):
    _driver = None
    _cameras = {}
    _assigned_cameras = set()

    def __init__(self,
                 name='Generic SDK camera',
                 driver=AbstractSDKDriver,
                 library_path=None,
                 filter_type=None,
                 target_temperature=None,
                 *args, **kwargs):
        # Would usually use self.logger but that won't exist until after calling super().__init__(),
        # and don't want to do that until after the serial number and port have both been determined
        # in order to avoid log entries with misleading values. To enable logging during the device
        # scanning phase use get_root_logger() instead.
        logger = get_root_logger()

        # The SDK cameras don't generally have a 'port', they are identified by a serial_number,
        # which is some form of unique ID readable via the camera SDK.
        kwargs['port'] = None
        serial_number = kwargs.get('serial_number')
        if not serial_number:
            msg = "Must specify serial_number for {}.".format(name)
            logger.error(msg)
            raise ValueError(msg)

        # Get class of current object in a way that works in derived classes
        my_class = type(self)

        if my_class._driver is None:
            # Initialise the driver if it hasn't already been done
            my_class._driver = driver(library_path=library_path, *args, **kwargs)

        logger.debug("Looking for {} with UID '{}'.".format(name, serial_number))

        if not my_class._cameras:
            # No cached camera details, need to probe for connected cameras
            # This will raise a PanError if there are no cameras.
            my_class._cameras = my_class._driver.get_cameras()
            logger.debug("Connected {}s: {}".format(name, my_class._cameras))

        if serial_number in my_class._cameras:
            logger.debug("Found {} with UID '{}' at {}.".format(
                name, serial_number, my_class._cameras[serial_number]))
        else:
            raise error.PanError("Could not find {} with UID '{}'.".format(
                name, serial_number))

        if serial_number in my_class._assigned_cameras:
            raise error.PanError("{} with UID '{}' already in use.".format(
                name, serial_number))

        my_class._assigned_cameras.add(serial_number)
        super().__init__(name, *args, **kwargs)
        self._address = my_class._cameras[self.uid]
        self.connect()
        if not self.is_connected:
            raise error.PanError("Could not connect to {}.".format(self))

        if filter_type:
            # connect() will have set this based on camera info, but that doesn't know about filters
            # upstream of the CCD. Can be set manually here, or handled by a filterwheel attribute.
            self._filter_type = filter_type

        if target_temperature is not None:
            self.target_temperature = target_temperature
            if self.is_cooled_camera:
                self.cooling_enabled = True
            else:
                msg = "Setting a target temperature on uncooled camera {}".format(self)
                self.logger.warning(msg)

    def __del__(self):
        """ Attempt some clean up """
        with suppress(AttributeError):
            uid = self.uid
            type(self)._assigned_cameras.discard(uid)
            self.logger.debug('Removed {} from assigned cameras list'.format(uid))

    # Properties

    @property
    def properties(self):
        """ A collection of camera properties as read from the camera """
        return self._info

    # Methods

    def _create_fits_header(self, seconds, dark):
        header = super()._create_fits_header(seconds, dark)
        header.set('CAM-SDK', type(self)._driver.version, 'Camera SDK version')
        return header

    def __str__(self):
        # SDK cameras don't have a port so just include the serial number in the string
        # representation.
        s = "{} ({})".format(self.name, self.uid)

        if self.focuser:
            s += ' with {}'.format(self.focuser.name)
            if self.filterwheel:
                s += ' & {}'.format(self.filterwheel.name)
        elif self.filterwheel:
            s += ' with {}'.format(self.filterwheel.name)

        return s
