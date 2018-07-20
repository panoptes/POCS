from time import time
from warnings import warn
from threading import Event
from threading import Timer
from threading import Thread
from threading import Lock

from astropy import units as u
import Pyro4

from pocs.base import PanBase
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

# Methods

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      timeout=None,
                      *args,
                      **kwargs):
        """
        Take an exposure for given number of seconds and saves to provided filename.

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
        # Want exposure time as a builtin type for Pyro serialisation
        if isinstance(seconds, u.Quantity):
            seconds = seconds.to(u.second)
            seconds = seconds.value

        # Find registered cameras and start exposure on each.
        cameras = self._name_server.list(metadata_all={'POCS', 'Camera'})
        exposure_results = {}
        for cam_name, cam_uri in cameras.items():
            self.logger.debug('Taking {} second exposure on {}: {}'.format(seconds,
                                                                           cam_name,
                                                                           filename))
            with Pyro4.Proxy(cam_uri) as cam_proxy:
                # Put the proxy into async mode
                Pyro4.async(cam_proxy)
                exposure_results[cam_name] = cam_proxy.take_exposure(seconds=seconds,
                                                                     filename=filename,
                                                                     dark=dark,
                                                                     blocking=True,
                                                                     *args,
                                                                     **kwargs)
        # Start a thread that will set an event once all exposures have completed
        exposure_event = Event()
        exposure_thread = Timer(interval=seconds,
                                function=self._async_wait,
                                args=(exposure_results, exposure_event, timeout))
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
                # Put the proxy into async mode
                Pyro4.async(cam_proxy)
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

    def _async_wait(self, async_results, async_event, timeout=None):
        if timeout is not None:
            if isinstance(timeout, u.Quantity):
                timeout = timeout.to(u.second)
                timeout = timeout.value
        # For now not checking for any problems, just wait for everything to return (or timeout)
        for result in async_results.values():
            if timeout is not None:
                wait_start_time = time()
            result.wait(timeout)
            if timeout is not None:
                # Need to adjust timeout, otherwise we're resetting the clock each time a
                # result returns.
                waited = time() - wait_start_time
                if waited < timeout:
                    timeout = timeout - waited
                else:
                    timeout = 0

        async_event.set()

    def _get_name_server(self):
        """
        Tries to find Pyro name server and returns a proxy to it.
        """
        name_server = None
        try:
            name_server = Pyro4.locateNS()
        except Pyro4.errors.NamingError:
            err = "No Pyro name server found!"
            self.logger.error(err)
            raise RuntimeError(err)

        return name_server


class CameraServer(PanBase):
    """
    Wrapper for the camera class for use as a Pyro camera server
    """
    def __init__(self):
        # Pyro classes ideally have no constructor arguments. Do it all from config file.
        super().__init__()
