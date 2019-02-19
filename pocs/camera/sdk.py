from pocs.base import PanBase
from pocs.camera.camera import AbstractCamera
from pocs.utils import error
from pocs.utils.library import load_library


class AbstractSDKDriver(PanBase):
    def __init__(self, name, library_path=None, **kwargs):
        """Base class for all camera SDK interfaces.

        On construction loads the shared object/dynamically linked version of the camera SDK
        library, which must be already installed.

        The name and location of the shared library can be manually specified with the library_path
        argument, otherwise the ctypes.util.find_library function will be used to try to locate it.

        Args:
            name (str): name of the library (without 'lib' prefix or any suffixes, e.g. 'fli').
            library_path (str, optional): path to the libary e.g. '/usr/local/lib/libASICamera2.so'

        Returns:
            `~pocs.camera.libasi.ASIDriver`

        Raises:
            pocs.utils.error.NotFound: raised if library_path not given & find_libary fails to
                locate the library.
            OSError: raises if the ctypes.CDLL loader cannot load the library.
        """
        super().__init__(**kwargs)
        self._CDLL = load_library(name=name, path=library_path, logger=self.logger)
        self._version = self.get_SDK_version()

    # Properties

    @property
    def version(self):
        return self._version

    # Methods

    def get_SDK_version(self):
        """ Get the version of the SDK """
        raise NotImplementedError

    def get_cameras(self):
        """Convenience function to get a dictionary of all currently connected camera UIDs
        and their corresponding device nodes/handles/camera IDs.
        """
        raise NotImplementedError


class AbstractSDKCamera(AbstractCamera):
    _driver = None
    _cameras = {}
    _assigned_cameras = set()

    def __init__(self,
                 name='Generic SDK camera',
                 driver=AbstractSDKDriver,
                 library_path=None,
                 filter_type=None,
                 set_point=None,
                 *args, **kwargs):
        # Would usually use self.logger but that won't exist until after calling super().__init__(),
        # and don't want to do that until after the serial number and port have both been determined
        # in order to avoid log entries with misleading values. To enable logging during the device
        # scanning phase use get_root_logger() instead.
        logger = get_root_logger()

        # The SDK cameras don't have a 'port', they are identified by a serial_number, which
        # is some form of unique ID readable via the camera SDK.
        kwargs['port'] = None
        serial_number = kwargs.get('serial_number')
        if not serial_number:
            msg = "Must specify serial_number for {}.".format(name)
            logger.error(msg)
            raise ValueError(msg)

        if type(self)._driver is None:
            # Initialise the driver if it hasn't already been done
            type(self)._driver = driver(library_path=library_path)

        logger.debug("Looking for {} with UID '{}'.".format(name, serial_number))

        if not type(self)._cameras:
            # No cached camera details, need to probe for connected cameras
            type(self)._cameras = type(self)._driver.get_cameras()

        if serial_number in type(self)._cameras:
            logger.debug("Found {} with UID '{}' at {}.".format(
                name, serial_number, type(self)._cameras[serial_number]))
        else:
            raise error.PanError("Could not find {} with UID '{}'.".format(
                name, serial_number))

        if serial_number in type(self)._assigned_cameras:
            raise error.PanError("{} with UID '{}' already in use.".format(
                name, serial_number))

        type(self)._assigned_cameras.add(serial_number)
        super().__init__(name, *args, **kwargs)
        self.connect()
        assert self.is_connected, error.PanError("Could not connect to {}.".format(self))

        if filter_type:
            # connect() will have set this based on camera info, but that doesn't know about filters
            # upstream of the CCD. Can be set manually here, or handled by a filterwheel attribute.
            self._filter_type = filter_type

        if set_point:
            self.ccd_set_point = set_point
            self.ccd_cooling_enabled = True

    def __del__(self):
        """ Attempt some clean up """
        with suppress(AttributeError):
            uid = self.uid
            type(self)._assigned_cameras.discard(uid)
            self.logger.debug('Removed {} from assigned cameras list'.format(uid))
        super().__del__()
