import time

from astropy.coordinates import SkyCoord

from ..utils.config import load_config
from .mount import AbstractMount


class Mount(AbstractMount):

    """Mount class for a simulator. Use this when you don't actually have a mount attached.
    """

    def __init__(self,
                 config=dict(),
                 commands=dict(),
                 location=None,
                 *args, **kwargs
                 ):

        super().__init__(*args, **kwargs)

        self.logger.info('\t\tUsing simulator mount')

        self._loop_delay = self.mount_config.get('loop_delay', 7.0)

        self.config = load_config()

        self.logger.debug('Simulator mount created')


##################################################################################################
# Properties
##################################################################################################

##################################################################################################
# Public Methods
##################################################################################################

    def initialize(self):
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
        self._is_connected = True
        self._is_initialized = True

        return self.is_initialized

    def connect(self):
        self.logger.debug("Connecting to mount simulator")
        self._is_connected = True
        return True

    def unpark(self):
        self.logger.debug("Unparking mount")
        self._is_connected = True
        self._is_parked = False
        return True

    def move_direction(self, direction='north', seconds=1.0):
        """ Move mount in specified `direction` for given amount of `seconds`

        """
        self.logger.debug("Mount simulator moving {} for {} seconds".format(direction, seconds))
        time.sleep(seconds)

    def status(self):

        status = {

        }

        return status

    def set_target_coordinates(self, coords):
        """ Sets the RA and Dec for the mount's current target.

        Args:
            coords (astropy.coordinates.SkyCoord): coordinates specifying target location

        Returns:
            bool:  Boolean indicating success
        """
        self.logger.debug("Setting coords to {}".format(coords))
        self._target_coordinates = coords

        return True

    def get_current_coordinates(self):
        """ Returns some coordinates

        Note:
            These are totally random for now

        Returns:
            astropy.coordinates.SkyCoord
        """

        # Turn the mount coordinates into a SkyCoord
        self._current_coordinates = SkyCoord.from_name('M42')

        return self._current_coordinates

    def slew_to_target(self):
        self.logger.debug("Slewing for {} seconds".format(self._loop_delay))

        self._is_slewing = True
        self._is_tracking = False
        self._is_home = False

        while self._loop_delay:
            time.sleep(1)
            self._loop_delay = self._loop_delay - 1

        self.stop_slew()

        return True

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

    def slew_to_home(self):
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

    def set_park(self):
        """ Sets the mount to park for simulator """
        self.logger.debug("Setting to park")
        self._is_slewing = False
        self._is_tracking = False
        self._is_home = False
        self._is_parked = True

    def home_and_park(self):
        """ Convenience method to first slew to the home position and then park. """
        self.logger.info("Going home then parking")
        self.slew_to_home()
        self.set_park()

    def serial_query(self, cmd, *args):
        self.logger.debug("Serial query: {} {}".format(cmd, args))

    def serial_write(self, cmd):
        self.logger.debug("Serial write: {}".format(cmd))

    def serial_read(self):
        self.logger.debug("Serial read")


##################################################################################################
# Private Methods
##################################################################################################

    def _setup_location_for_mount(self):
        """Sets the mount up to the current location. Mount must be initialized first. """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')
        assert self.location is not None, self.logger.warning('Please set a location before attempting setup')

        self.logger.debug('Setting up mount for location')

    def _mount_coord_to_skycoord(self, mount_coords):
        """ Returns same coords """
        return mount_coords

    def _skycoord_to_mount_coord(self, coords):
        """ Returns same coords """

        return coords

    def _set_zero_position(self):
        """ Sets the current position as the zero position. """
        self.logger.debug("Simulator cannot set zero position")
        return False

    def _setup_commands(self, commands):
        return commands
