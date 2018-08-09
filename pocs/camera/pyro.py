import os
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
from pocs.utils import config
from pocs.utils.logger import get_root_logger
from pocs.utils import load_module
from pocs.camera import AbstractCamera


class Camera(AbstractCamera):
    """
    Class representing the client side interface to a distributed array of cameras
    """
    def __init__(self,
                 name='Pyro Camera Array',
                 model='pyro',
                 *args, **kwargs):
        super().__init__(name=name, model=model, *args, **kwargs)

        # Get a proxy for the name server (will raise NamingError if not found)
        self._name_server = Pyro4.locateNS()
        # Connect to cameras
        self.connect()

# Methods

    def connect(self):
        """
        Find and (re)connect to all the distributed cameras.
        """
        # Find all the registered cameras.
        camera_uris = self._name_server.list(metadata_all={'POCS', 'Camera'})
        msg = "Found {} cameras registered with Pyro name server".format(len(camera_uris))
        self.logger.debug(msg)

        # Get a proxy for each camera
        self.cameras = {}
        for cam_name, cam_uri in camera_uris.items():
            self.logger.debug("Getting proxy for {}...".format(cam_name))
            try:
                self.cameras[cam_name] = Pyro4.Proxy(cam_uri)
            except Pyro4.errors.NamingError as err:
                msg = "Couldn't get proxy to camera {}: {}".format(cam_nam, err)
                warn(msg)
                self.logger.error(msg)
                self.cameras.remove(cam_name)
            else:
                # Set aync mode
                self.cameras[cam_name]._pyroAsync()

        # Force each camera proxy to connect by getting the camera uids.
        # This will trigger the remote object creation & (re)initialise the camera & focuser,
        # which can take a long time with real hardware, so do this in parallel.
        async_results = {}
        for cam_name, cam_proxy in self.cameras.items():
            self.logger.debug("Connecting to {}...".format(cam_name))
            async_results[cam_name] = cam_proxy.get_uid()

        self.uids = {}
        for cam_name, result in async_results.items():
            self.uids[cam_name] = result.value

        self.logger.debug("Got camera UIDs: {}".format(self.uids))

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      timeout=None,
                      *args,
                      **kwargs):
        """
        Take exposures for a given number of seconds and saves to provided filename.

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
            dark (bool, optional): Exposure is a dark frame (don't open shutter), default False
            blocking (bool, optional): If False (default) returns immediately after starting
                the exposure, if True will block until it completes.
            timeout (u.second, optional): Length of time beyond the length the exposure to wait
                for exposures to complete. If not given will wait indefinitely.

        Returns:
            threading.Event: Event that will be set when exposures are complete

        """
        # Want exposure time as a builtin type for Pyro serialisation
        if isinstance(seconds, u.Quantity):
            seconds = seconds.to(u.second)
            seconds = seconds.value

        if timeout is not None:
            if isinstance(timeout, u.Quantity):
                timeout = timeout.to(u.second)
                timeout = timeout.value

        # Find somewhere to insert the indivudual camera UIDs
        if "<uid>" in filename:
            dir_name, base_name = filename.split(sep="<uid>", maxsplit=1)
        else:
            dir_name, base_name = os.path.split(filename)

        # Start the exposure on all cameras
        exposure_results = {}
        for cam_name, cam_proxy in self.cameras.items():
            self.logger.debug('Taking {} second exposure on {}: {}'.format(seconds,
                                                                           cam_name,
                                                                           base_name))
            # Remote method call to start the exposure
            future_result = cam_proxy.take_exposure(seconds=seconds,
                                                    base_name=base_name,
                                                    dark=dark,
                                                    *args,
                                                    **kwargs)
            # Tag the file transfer on the end, and keep future result to check for completion
            destination = os.path.join(dir_name, self.uids[cam_name], base_name)
            exposure_results[cam_name] = future_result.then(self._file_transfer,
                                                            destination)

        # Start a thread that will set an event once all exposures have completed
        exposure_event = Event()
        exposure_thread = Timer(interval=seconds,
                                function=self._async_wait,
                                args=(exposure_results, 'exposure', exposure_event, timeout))
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
                  spline_smoothing=None,
                  coarse=False,
                  plots=True,
                  blocking=False,
                  timeout=None,
                  *args, **kwargs):
        """
        Focuses the camera using the specified merit function. Optionally
        performs a coarse focus first before performing the default fine focus.
        The expectation is that coarse focus will only be required for first use
        of a optic to establish the approximate position of infinity focus and
        after updating the intial focus position in the config only fine focus
        will be required.

        Args:
            seconds (optional): Exposure time for focus exposures, if not
                specified will use value from config.
            focus_range (2-tuple, optional): Coarse & fine focus sweep range, in
                encoder units. Specify to override values from config.
            focus_step (2-tuple, optional): Coarse & fine focus sweep steps, in
                encoder units. Specify to override values from config.
            thumbnail_size (optional): Size of square central region of image to
                use, default 500 x 500 pixels.
            keep_files (bool, optional): If True will keep all images taken
                during focusing. If False (default) will delete all except the
                first and last images from each focus run.
            take_dark (bool, optional): If True will attempt to take a dark frame
                before the focus run, and use it for dark subtraction and hot
                pixel masking, default True.
            merit_function (str/callable, optional): Merit function to use as a
                focus metric.
            merit_function_kwargs (dict, optional): Dictionary of additional
                keyword arguments for the merit function.
            mask_dilations (int, optional): Number of iterations of dilation to perform on the
                saturated pixel mask (determine size of masked regions), default 10
            spline_smoothing (float, optional): smoothing parameter for the spline fitting to
                the autofocus data, 0.0 to 1.0, smaller values mean *less* smoothing, default 0.4
            coarse (bool, optional): Whether to begin with coarse focusing,
                default False
            plots (bool, optional: Whether to write focus plots to images folder,
                default True.
            blocking (bool, optional): Whether to block until autofocus complete,
                default False
            timeout (u.second, optional): Total length of time to wait for autofocus sequences
                to complete. If not given will wait indefinitely.

        Returns:
            threading.Event: Event that will be set when autofocusing is complete
        """
        autofocus_kwargs = {'seconds': seconds,
                            'focus_range': focus_range,
                            'focus_step': focus_step,
                            'keep_files': keep_files,
                            'take_dark': take_dark,
                            'thumbnail_size': thumbnail_size,
                            'merit_function': merit_function,
                            'merit_function_kwargs': merit_function_kwargs,
                            'mask_dilations': mask_dilations,
                            'spline_smoothing': spline_smoothing,
                            'coarse': coarse,
                            'plots': plots,
                            'blocking': True}

        # Find registered cameras and start autofocus on each.
        cameras = self._name_server.list(metadata_all={'POCS', 'Camera'})
        autofocus_results = {}
        for cam_name, cam_uri in cameras.items():
            self.logger.debug('Starting autofocus on {}'.format(cam_name))
            with Pyro4.Proxy(cam_uri) as cam_proxy:
                autofocus_results[cam_name] = cam_proxy.autofocus(*args,
                                                                  **autofocus_kwargs,
                                                                  **kwargs)

        # Start a thread that will set an event once all exposures have completed
        autofocus_event = Event()
        autofocus_thread = Thread(function=self._async_wait,
                                  args=(autofocus_results, autofocus_event, timeout))
        autofocus_thread.start()

        if blocking:
            autofocus_event.wait()

        return autofocus_event

# Private Methods

    def _file_transfer(self, source, destination):
        """
        Used rsync to move a file from source to destination.
        """
        try:
            result = subprocess.run(['rsync',
                                     '-ah',
                                     '--remove-source-files',
                                     source,
                                     destination],
                                    check=True)
        except subprocess.CalledProcessError as err:
            msg = "File transfer {} -> {} failed".format(source, destination)
            warn(msg)
            self.logger.error(msg)
            raise err

    def _async_wait(self, future_results, method='?', event=None, timeout=None):
        # For now not checking for any problems, just wait for everything to return (or timeout)
        results = {}
        if timeout is not None:
            wait_start_time = time.time()

        for name, future_result in future_results.items():
            if future_result.wait(timeout):
                results[name] = future_result.value
            else:
                msg = "Timeout while waiting for {} on {}".format(method, name)
                warn(msg)
                self.logger.error(msg)
            if timeout is not None:
                # Need to adjust timeout, otherwise we're resetting the clock each time a
                # single result returns.
                waited = time.time() - wait_start_time
                if waited < timeout:
                    timeout = timeout - waited
                else:
                    timeout = 0

        if event is not None:
            event.set()

        return results


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
        camera_model = camera_config.get('model')
        camera_port = camera_config.get('port')
        camera_set_point = camera_config.get('set_point', None)
        camera_filter_type = camera_config.get('filter_type', None)
        camera_readout_time = camera_config.get('readout_time', None)
        camera_focuser = camera_config.get('focuser', None)

        module = load_module('pocs.camera.{}'.format(camera_model))
        self._camera = module.Camera(name=self.name,
                                     model=camera_model,
                                     port=camera_port,
                                     set_point=camera_set_point,
                                     filter_type=camera_filter_type,
                                     focuser=camera_focuser,
                                     readout_time=camera_readout_time,
                                     logger=get_root_logger(self.name))

# Properties

    @property
    def uid(self):
        return self._camera.uid

# Methods

    def get_uid(self):
        """
        Added as an alternative to accessing the uid property because that didn't trigger
        object creation.
        """
        return self._camera.uid

    def take_exposure(self, seconds, base_name, dark, *args, **kwargs):
        filename = os.path.join(os.getenv('PANDIR', '/var/panoptes'),
                                'temp',
                                base_name)
        # Start the exposure and wait for it complete
        self._camera.take_exposure(seconds, filename, dark, blocking=True, *args, **kwargs)
        # Return the user@host:/path for created file to enable it to be moved over the network.
        return "{}@{}:{}".format(self.user, self.host, os.path.abspath(filename))

# Private methods
