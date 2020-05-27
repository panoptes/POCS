import time
from threading import Timer

from astropy import units as u

from panoptes.utils import current_time
from panoptes.utils import error
from panoptes.pocs.mount import AbstractMount


class Mount(AbstractMount):

    """Mount class for a simulator. Use this when you don't actually have a mount attached.
    """

    def __init__(self, location, commands=dict(), *args, **kwargs):

        super().__init__(location, *args, **kwargs)

        self.logger.info('\t\tUsing simulator mount')

        self._loop_delay = self.get_config('loop_delay', default=0.01)

        self.set_park_coordinates()
        self._current_coordinates = self._park_coordinates

        self.logger.debug('Simulator mount created')


##################################################################################################
# Properties
##################################################################################################

##################################################################################################
# Public Methods
##################################################################################################

    def initialize(self, unpark=False, *arg, **kwargs):
        """ Initialize the connection with the mount and setup for location.

        iOptron mounts are initialized by sending the following two commands
        to the mount:e

        * Version
        * MountInfo

        If the mount is successfully initialized, the `_setup_location_for_mount` method
        is also called.

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

        return self.is_initialized

    def connect(self):
        self.logger.debug("Connecting to mount simulator")
        self._is_connected = True
        return True

    def disconnect(self):
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
        self.logger.debug("Mount simulator moving {} for {} seconds".format(direction, seconds))
        time.sleep(seconds)

    def get_ms_offset(self, offset, axis='ra'):
        """ Fake offset in milliseconds

        Args:
            offset (astropy.units.Angle): Offset in arcseconds

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

        self._current_coordinates = self.get_target_coordinates()

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

    def slew_to_home(self, blocking=False):
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

    def park(self):
        """ Sets the mount to park for simulator """
        self.logger.debug("Setting to park")
        self._state = 'Parked'
        self._is_slewing = False
        self._is_tracking = False
        self._is_home = False
        self._is_parked = True

    def unpark(self):
        self.logger.debug("Unparking mount")
        self._is_connected = True
        self._is_parked = False
        return True

    def query(self, cmd, params=None):
        self.logger.debug(f"Query cmd: {cmd} params: {params!r}")
        if cmd == 'slew_to_target':
            time.sleep(self._loop_delay)

        return True

    def write(self, cmd):
        self.logger.debug("Write: {}".format(cmd))

    def read(self, *args):
        self.logger.debug("Read")

    def set_tracking_rate(self, direction='ra', delta=0.0):
        self.logger.debug('Setting tracking rate delta: {} {}'.format(direction, delta))
        self.tracking = 'Custom'
        self.tracking_rate = 1.0 + delta
        self.logger.debug("Custom tracking rate sent")


##################################################################################################
# Private Methods
##################################################################################################

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

    def _setup_commands(self, commands):
        return commands
