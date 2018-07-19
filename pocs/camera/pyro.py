from threading import Event
from threading import Timer
from threading import Lock

from astropy import units as u
import Pyro4

from pocs.camera import AbstractCamera


class Camera(AbstractCamera):
    """
    Class representing the interface to a distributed array of cameras
    """
    def __init__(self,
                 name='Pyro Camera Array',
                 model='pyro',
                 *args, **kwargs):
        super().__init__(name=name, model=model, *args, **kwargs)

        # Get a proxy for the name server (will raise NamingError if not found)
        self._name_server = Pyro4.locateNS()

        # Create a Lock that will be used to prevent overlapping exposures.
        self._exposure_lock = Lock()

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
                for exposures to complete. If

        Returns:
            threading.Event: Event that will be set when exposure is complete

        """
        # Want exposure time as a builtin type for Pyro serialisation
        if isinstance(seconds, u.Quantity):
            seconds = seconds.to(u.second)
            seconds = seconds.value

        if not self._exposure_lock.acquire(blocking=False):
            message = 'Attempt to start exposure while exposure in progress! Waiting...'
            self.logger.warning(message)
            warn(message)
            self._exposure_lock.acquire(blocking=True)

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
                exposure_results[cam_name] = cam_proxy.take_exposure(seconds,
                                                                     filename,
                                                                     dark,
                                                                     *args,
                                                                     **kwargs)
        # Start a thread that will set an event once all exposures have completed
        exposure_event = Event()
        exposure_thread = Timer(interval=seconds,
                                function=self._exposure_wait,
                                args=(exposure_results, exposure_event))
        exposure_thread.start()

        if blocking:
            exposure_event.wait()

        return exposure_event

# Private Methods

    def _exposure_wait(self, exposure_results, exposure_event, timeout=None):
        if timeout is not None:
            if isinstance(timeout, u.Quantity):
                timeout = timeot.to(u.second)
                timeout = timeout.value
        # For now not checking for any problems with the exposures, just wait for them all to
        # end (or timeout).
        for result in exposure_results.values():
            result.wait(timeout=None)
        self._exposure_lock.release()
        exposure_event.set()

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
