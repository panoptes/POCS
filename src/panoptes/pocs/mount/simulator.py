import time
from contextlib import suppress
from threading import Timer
from typing import Tuple, Optional, Dict

from astropy import units as u
from astropy.coordinates import EarthLocation
from panoptes.pocs.utils.location import create_location_from_config
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config, set_config
from panoptes.utils.library import load_module

from panoptes.utils.time import current_time
from panoptes.utils import error
from panoptes.pocs.mount.base import AbstractMount


class Mount(AbstractMount):
    """Mount class for a simulator. Really a SerialMount simulator.

    Use this when you don't actually have a mount attached.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.info('Using simulator mount')

        self._loop_delay = self.get_config('loop_delay', default=0.01)

        self.set_park_coordinates()
        self._current_coordinates = self._park_coordinates

        self.logger.success('Simulator mount created')

    def initialize(self, unpark=False, *arg, **kwargs):
        """ Initialize the connection with the mount and setup for location.

        Returns:
            bool:   Returns the value from `self._is_initialized`.
        """
        self.logger.debug("Initializing simulator mount")

        if not self.is_connected:
            self.connect()

        self._is_initialized = True
        self._setup_location_for_mount()

        if unpark:
            self.unpark()

        return self._is_initialized

    def connect(self):
        self.logger.debug("Connecting to mount simulator")
        self._is_connected = True
        return True

    def disconnect(self, **kwargs):
        self.logger.debug("Disconnecting mount simulator")
        self._is_connected = False
        return True

    def _update_status(self):
        self.logger.debug("Getting mount simulator status")

        status = dict()

        status['timestamp'] = current_time()
        status['tracking_rate_ra'] = self.tracking_rate
        status['state'] = self.state

        return status

    def move_direction(self, direction='north', seconds=1.0):
        """ Move mount in specified `direction` for given amount of `seconds`

        """
        self.logger.debug(f'Mount simulator moving {direction} for {seconds} seconds')
        time.sleep(seconds)

    def get_ms_offset(self, offset, axis='ra'):
        """ Fake offset in milliseconds

        Args:
            offset (astropy.units.Angle): Offset in arcseconds
            axis (str): The axis to get offset for, options 'ra' (default) or 'dec'.

        Returns:
             astropy.units.Quantity: Offset in milliseconds at current speed
        """

        offset = 25 * u.arcsecond  # Fake value

        return super().get_ms_offset(offset, axis=axis)

    def slew_to_target(self, slew_delay=0.5, *args, **kwargs):
        self._is_tracking = False

        # Set up a timer to trigger the `is_tracking` property.
        def trigger_tracking():
            self.logger.debug('Triggering mount simulator tracking')
            self._is_tracking = True

        timer = Timer(slew_delay, trigger_tracking)
        timer.start()

        try:
            success = super().slew_to_target(*args, **kwargs)
        except error.Timeout:
            # Cancel the timer and re-throw exception
            timer.cancel()
            raise error.Timeout

        self._current_coordinates = self.target_coordinates

        return success

    def get_current_coordinates(self):
        return self._current_coordinates

    def stop_slew(self, next_position='is_tracking'):
        self.logger.debug("Stopping slewing")

        # Set all to false then switch one below
        self._is_slewing = False
        self._is_tracking = False
        self._is_home = False

        # We actually set the hidden variable directly
        next_position = "_" + next_position

        if hasattr(self, next_position):
            self.logger.debug("Setting next position to {}".format(next_position))
            setattr(self, next_position, True)

    def slew_to_home(self, blocking=False, **kwargs):
        """ Slews the mount to the home position.

        Note:
            Home position and Park position are not the same thing

        Returns:
            bool: indicating success
        """
        self.logger.debug("Slewing to home")
        self._is_slewing = True
        self._is_tracking = False
        self._is_home = False
        self._is_parked = False

        self.stop_slew(next_position='is_home')

    def park(self, **kwargs):
        """ Sets the mount to park for simulator """
        self.logger.debug("Setting to park")
        self._state = 'Parked'
        self._is_slewing = False
        self._is_tracking = False
        self._is_home = False
        self._is_parked = True

    def unpark(self):
        self.logger.debug('Unparking mount')
        self._is_connected = True
        self._is_parked = False
        return True

    def query(self, cmd, params=None):
        self.logger.debug(f'Query cmd: {cmd} params: {params!r}')
        if cmd == 'slew_to_target':
            time.sleep(self._loop_delay)

        return True

    def write(self, cmd):
        self.logger.debug(f'Write: {cmd}')

    def read(self):
        self.logger.debug('Read')

    def set_tracking_rate(self, direction='ra', delta=0.0):
        self.logger.debug(f'Setting tracking rate delta: {direction} {delta}')
        self.tracking_mode = 'Custom'
        self.tracking_rate = 1.0 + delta
        self.logger.debug("Custom tracking rate sent")

    def _setup_location_for_mount(self):
        """Sets the mount up to the current location. Mount must be initialized first. """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')
        assert self.location is not None, self.logger.warning(
            'Please set a location before attempting setup')

        self.logger.debug('Setting up mount for location')

    def _mount_coord_to_skycoord(self, mount_coords):
        """ Returns same coords """
        return mount_coords

    def _skycoord_to_mount_coord(self, coords):
        """ Returns same coords """

        return [coords.ra, coords.dec]

    def _set_zero_position(self):
        """ Sets the current position as the zero position. """
        self.logger.debug("Simulator cannot set zero position")
        return False

    def _setup_commands(self, commands: Optional[dict] = None) -> Dict:
        return commands

    def get_tracking_correction(self,
                                offset_info: Tuple[float, float],
                                pointing_ha: float,
                                thresholds: Optional[Tuple[int, int]] = None
                                ) -> Dict[str, Tuple[float, float, str]]:
        pass

    def correct_tracking(self, correction_info, axis_timeout=30.):
        pass

    def set_target_coordinates(self, new_coord):
        pass

    def _get_command(self, cmd, params=None):
        pass

    def _set_initial_rates(self):
        pass

    @classmethod
    def create_mount_simulator(cls,
                               mount_info: Optional[Dict] = None,
                               earth_location: Optional[EarthLocation] = None,
                               *args,
                               **kwargs) -> AbstractMount:
        """Create a mount simulator.

        Args:
            mount_info (Dict): The mount config.
            earth_location (EarthLocation):
            db_type (str):
            *args:
            **kwargs:

        Returns:
            Mount: An instance of the simulator mount.
        """
        logger = kwargs.get('logger', get_logger())

        earth_location = earth_location or create_location_from_config()['earth_location']
        logger.debug(f'Using {earth_location=!r}')

        mount_config = mount_info or get_config('mount', {})
        logger.debug(f'Using {mount_config=!r}')
        driver = mount_config.get('driver', 'panoptes.pocs.mount.simulator')
        try:
            module = load_module(driver)
        except error.NotFound as e:
            raise error.MountNotFound(f'Error loading mount module: {e!r}')

        mount = module.Mount(earth_location, *args, **kwargs)
        logger.success(f'{mount} created')

        return mount
