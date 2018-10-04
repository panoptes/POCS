import sys
import os
import glob
import time
from warnings import warn
from threading import Event
from threading import Timer
from threading import Thread
from threading import Lock
import subprocess

from astropy import units as u
import Pyro4

from pocs.base import PanBase
from pocs.utils import current_time
from pocs.utils import config
from pocs.utils.logger import get_root_logger
from pocs.utils import load_module
from pocs.camera import AbstractCamera


# Enable local display of remote tracebacks
sys.excepthook = Pyro4.util.excepthook


class Camera(AbstractCamera):
    """
    Class representing the client side interface to a distributed camera
    """
    def __init__(self,
                 uri,
                 name='Pyro Camera',
                 model='pyro',
                 *args, **kwargs):
        super().__init__(name=name, port=uri, model=model, *args, **kwargs)

        # Connect to camera
        self.connect(uri)

# Properties

    @AbstractCamera.uid.getter
    def uid(self):
        # Neet to overide this because the base class only returns the 1st 6 characters of the
        # serial number, which is not a unique identifier for most of the camera types.
        return self._serial_number

    @property
    def ccd_temp(self):
        """
        Current temperature of the camera's image sensor.
        """
        return self._proxy.ccd_temp * u.Celsius

    @property
    def ccd_set_point(self):
        """
        Current value of the CCD set point, the target temperature for the camera's
        image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity.
        """
        return self._proxy.ccd_set_point * u.Celsius

    @ccd_set_point.setter
    def ccd_set_point(self, set_point):
        if isinstance(set_point, u.Quantity):
            set_point = set_point.to(u.Celsius).value
        self._proxy.ccd_set_point = set_point

    @property
    def ccd_cooling_enabled(self):
        """
        Current status of the camera's image sensor cooling system (enabled/disabled).

        For some cameras it is possible to change this by assigning a boolean
        """
        return self._proxy.ccd_cooling_enabled

    @ccd_cooling_enabled.setter
    def ccd_cooling_enabled(self, enabled):
        self._proxy.ccd_cooling_enabled = bool(enabled)

    @property
    def ccd_cooling_power(self):
        """
        Current power level of the camera's image sensor cooling system (typically as
        a percentage of the maximum).
        """
        return self._proxy.ccd_cooling_power

# Methods

    def connect(self, uri):
        """
        (re)connect to the distributed camera.
        """
        self.logger.debug('Connecting to {} on {}'.format(self.name, uri))

        # Get a proxy for the camera
        try:
            self._proxy = Pyro4.Proxy(uri)
        except Pyro4.errors.NamingError as err:
            msg = "Couldn't get proxy to camera {}: {}".format(self.name, err)
            warn(msg)
            self.logger.error(msg)
            return

        # Set sync mode
        Pyro4.async(self._proxy, async=False)

        # Force camera proxy to connect by getting the camera uid.
        # This will trigger the remote object creation & (re)initialise the camera & focuser,
        # which can take a long time with real hardware.
        uid = self._proxy.get_uid()
        if not uid:
            msg = "Couldn't connect to {} on {}!".format(self.name, uri)
            warn(msg)
            self.logger.error(msg)
            return

        self._connected = True
        self._serial_number = uid
        self.model = self._proxy.model
        self._file_extension = self._proxy.file_extension
        self._readout_time = self._proxy.readout_time
        self.filter_type = self._proxy.filter_type
        self.logger.debug("{} connected".format(self))

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      timeout=None,
                      *args,
                      **kwargs):
        """
        Take exposure for a given number of seconds and saves to provided filename.

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
            dark (bool, optional): Exposure is a dark frame (don't open shutter), default False
            blocking (bool, optional): If False (default) returns immediately after starting
                the exposure, if True will block until it completes.
            timeout (u.second, optional): Length of time beyond the length the exposure to wait
                for exposures to complete. If not given will wait indefinitely.

        Returns:
            threading.Event: Event that will be set when exposure is complete

        """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        # Want exposure time as a builtin type for Pyro serialisation
        if isinstance(seconds, u.Quantity):
            seconds = seconds.to(u.second)
            seconds = seconds.value

        if timeout is not None:
            if isinstance(timeout, u.Quantity):
                timeout = timeout.to(u.second)
                timeout = timeout.value

        dir_name, base_name = os.path.split(filename)
        # Make sure dir_name has one and only one trailing slash, otherwise rsync may fail
        dir_name = dir_name.rstrip('/') + '/'

        # Make sure proxy is in async mode
        Pyro4.async(self._proxy, async=True)

        # Start the exposure
        self.logger.debug('Taking {} second exposure on {}: {}'.format(
            seconds, self.name, base_name))
        # Remote method call to start the exposure
        exposure_result = self._proxy.take_exposure(seconds=seconds,
                                                    base_name=base_name,
                                                    dark=dark,
                                                    *args,
                                                    **kwargs)
        # Tag the file transfer on the end.
        exposure_result = exposure_result.then(self._file_transfer, dir_name)
        # Tag empty directory cleanup on the end & keep future result to check for completion
        exposure_result = exposure_result.then(self._clean_directories)

        # Start a thread that will set an event once exposure has completed
        exposure_event = Event()
        exposure_thread = Timer(interval=seconds + self.readout_time,
                                function=self._async_wait,
                                args=(exposure_result, 'exposure', exposure_event, timeout))
        exposure_thread.start()

        if blocking:
            exposure_event.wait()

        return exposure_event

    def autofocus(self,
                  seconds=None,
                  focus_range=None,
                  focus_step=None,
                  thumbnail_size=None,
                  keep_files=None,
                  take_dark=None,
                  merit_function='vollath_F4',
                  merit_function_kwargs={},
                  mask_dilations=None,
                  coarse=False,
                  make_plots=False,
                  blocking=False,
                  timeout=None,
                  *args, **kwargs):
        """
        Focuses the camera using the specified merit function. Optionally performs
        a coarse focus to find the approximate position of infinity focus, which
        should be followed by a fine focus before observing.

        Args:
            seconds (scalar, optional): Exposure time for focus exposures, if not
                specified will use value from config.
            focus_range (2-tuple, optional): Coarse & fine focus sweep range, in
                encoder units. Specify to override values from config.
            focus_step (2-tuple, optional): Coarse & fine focus sweep steps, in
                encoder units. Specify to override values from config.
            thumbnail_size (int, optional): Size of square central region of image
                to use, default 500 x 500 pixels.
            keep_files (bool, optional): If True will keep all images taken
                during focusing. If False (default) will delete all except the
                first and last images from each focus run.
            take_dark (bool, optional): If True will attempt to take a dark frame
                before the focus run, and use it for dark subtraction and hot
                pixel masking, default True.
            merit_function (str/callable, optional): Merit function to use as a
                focus metric, default vollath_F4.
            merit_function_kwargs (dict, optional): Dictionary of additional
                keyword arguments for the merit function.
            mask_dilations (int, optional): Number of iterations of dilation to perform on the
                saturated pixel mask (determine size of masked regions), default 10
            coarse (bool, optional): Whether to perform a coarse focus, otherwise will perform
                a fine focus. Default False.
            make_plots (bool, optional: Whether to write focus plots to images folder, default
                False.
            blocking (bool, optional): Whether to block until autofocus complete, default False.
            timeout (u.second, optional): Total length of time to wait for autofocus sequences
                to complete. If not given will wait indefinitely.

        Returns:
            threading.Event: Event that will be set when autofocusing is complete
        """
        # Make certain that all the argument are builtin types for easy Pyro serialisation
        if isinstance(seconds, u.Quantity):
            seconds = seconds.to(u.second)
            seconds = seconds.value

        if timeout is not None:
            if isinstance(timeout, u.Quantity):
                timeout = timeout.to(u.second)
                timeout = timeout.value

        autofocus_kwargs = {'seconds': seconds,
                            'focus_range': focus_range,
                            'focus_step': focus_step,
                            'keep_files': keep_files,
                            'take_dark': take_dark,
                            'thumbnail_size': thumbnail_size,
                            'merit_function': merit_function,
                            'merit_function_kwargs': merit_function_kwargs,
                            'mask_dilations': mask_dilations,
                            'coarse': coarse,
                            'make_plots': make_plots}

        focus_dir = os.path.join(os.path.abspath(self.config['directories']['images']), 'focus/')

        # Make sure proxy is in async mode
        Pyro4.async(self._proxy, async=True)

        # Start autofocus
        autofocus_result = {}
        self.logger.debug('Starting autofocus on {}'.format(self.name))
        # Remote method call to start the autofocus
        autofocus_result = self._proxy.autofocus(*args, **autofocus_kwargs, **kwargs)
        # Tag the file transfer on the end.
        autofocus_result = autofocus_result.then(self._file_transfer, focus_dir)
        # Tag empty directory cleanup on the end & keep future result to check for completion
        autofocus_result = autofocus_result.then(self._clean_directories)

        # Start a thread that will set an event once autofocus has completed
        autofocus_event = Event()
        autofocus_thread = Thread(target=self._async_wait,
                                  args=(autofocus_result, 'autofocus', autofocus_event, timeout))
        autofocus_thread.start()

        if blocking:
            autofocus_event.wait()

        return autofocus_event

# Private Methods

    def _clean_directories(self, source):
        """
        Clean up empty directories left behind by rsysc.
        """
        user_at_host, path = source.split(':')
        path_root = path.split('/./')[0]
        try:
            result = subprocess.run(['ssh',
                                     user_at_host,
                                     'find {} -empty -delete'.format(path_root)],
                                    check=True)
        except subprocess.CalledProcessError as err:
            msg = "Clean up of empty directories in {}:{} failed".format(user_at_host, path_root)
            warn(msg)
            self.logger.error(msg)
            raise err
        self.logger.debug("Clean up of empty directories in {}:{} complete".format(user_at_host,
                                                                                   path_root))
        return source

    def _file_transfer(self, source, destination):
        """
        Used rsync to move a file from source to destination.
        """
        # Need to make sure the destination directory already exists because rsync isn't
        # very good at creating directories.
        os.makedirs(os.path.dirname(destination), mode=0o775, exist_ok=True)
        try:
            result = subprocess.run(['rsync',
                                     '--archive',
                                     '--relative',
                                     '--recursive',
                                     '--remove-source-files',
                                     source,
                                     destination],
                                    check=True)
        except subprocess.CalledProcessError as err:
            msg = "File transfer {} -> {} failed".format(source, destination)
            warn(msg)
            self.logger.error(msg)
            raise err
        self.logger.debug("File transfer {} -> {} complete".format(source.split('/./')[1],
                                                                   destination))
        return source

    def _async_wait(self, future_result, name='?', event=None, timeout=None):
        # For now not checking for any problems, just wait for everything to return (or timeout)
        if future_result.wait(timeout):
            result = future_result.value
        else:
            msg = "Timeout while waiting for {} on {}".format(name, self.name)
            warn(msg)
            self.logger.error(msg)
            return False

        if event is not None:
            event.set()

        return result


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")
class CameraServer(object):
    """
    Wrapper for the camera class for use as a Pyro camera server
    """
    def __init__(self):
        # Pyro classes ideally have no arguments for the constructor. Do it all from config file.
        self.config = config.load_config(config_files=['pyro_camera.yaml'])
        self.name = self.config.get('name')
        self.host = self.config.get('host')
        self.port = self.config.get('port')
        self.user = os.getenv('PANUSER', 'panoptes')

        camera_config = self.config.get('camera')
        camera_config.update({'name': self.name,
                              'config': self.config})
        module = load_module('pocs.camera.{}'.format(camera_config['model']))
        self._camera = module.Camera(**camera_config)

# Properties

    @property
    def uid(self):
        return self._camera.uid

    @property
    def model(self):
        return self._camera.model

    @property
    def filter_type(self):
        return self._camera.filter_type

    @property
    def file_extension(self):
        return self._camera.file_extension

    @property
    def readout_time(self):
        return self._camera.readout_time

    @property
    def ccd_temp(self):
        temperature = self._camera.ccd_temp
        return temperature.to(u.Celsius).value

    @property
    def ccd_set_point(self):
        temperature = self._camera.ccd_set_point
        return temperature.to(u.Celsius).value

    @ccd_set_point.setter
    def ccd_set_point(self, set_point):
        self._camera.ccd_set_point = set_point

    @property
    def ccd_cooling_enabled(self):
        return self._camera.ccd_cooling_enabled

    @ccd_cooling_enabled.setter
    def ccd_cooling_enabled(self, enabled):
        self._camera.ccd_cooling_enabled = enabled

    @property
    def ccd_cooling_power(self):
        return self._camera.ccd_cooling_power

# Methods

    def get_uid(self):
        """
        Added as an alternative to accessing the uid property because that didn't trigger
        object creation.
        """
        return self._camera.uid

    def take_exposure(self, seconds, base_name, dark, *args, **kwargs):
        # Using the /./ syntax for partial relative paths (needs rsync >= 2.6.7)
        filename = os.path.join(os.path.abspath(self.config['directories']['images']),
                                './',
                                base_name)
        # Start the exposure and wait for it complete
        self._camera.take_exposure(seconds=seconds,
                                   filename=filename,
                                   dark=dark,
                                   blocking=True,
                                   *args,
                                   **kwargs)
        # Return the user@host:/path for created file to enable it to be moved over the network.
        return "{}@{}:{}".format(self.user, self.host, filename)

    def autofocus(self, *args, **kwargs):
        # Start the autofocus and wait for it to completed
        kwargs['blocking'] = True
        self._camera.autofocus(*args, **kwargs)
        # Find where the resulting files are. Need to cast a wide net to get both
        # coarse and fine focus files, anything in focus directory should be fair game.
        focus_path = os.path.join(os.path.abspath(self.config['directories']['images']),
                                  'focus/./',
                                  self.uid,
                                  '*')
        # Return the user@host:/path for created files to enable them to be moved over the network.
        return "{}@{}:{}".format(self.user, self.host, focus_path)
