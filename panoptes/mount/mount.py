import time

from astropy import units as u
from astropy.coordinates import SkyCoord

from ..utils.logger import get_logger
from ..utils import current_time


class AbstractMount(object):

    """
        Abstract Base class for controlling a mount. This provides the basic functionality
        for the mounts. Sub-classes should override the `initialize` method for mount-specific
        issues as well as any helper methods specific mounts might need. See "NotImplemented Methods"
        section of this module.

        Sets the following properies:

            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self._is_initialized = False

        Args:
            config (dict):              Custom configuration passed to base mount. This is usually
                                        read from the main system config.

            commands (dict):            Commands for the telescope. These are read from a yaml file
                                        that maps the mount-specific commands to common commands.

            location (EarthLocation):   An astropy.coordinates.EarthLocation that contains location information.

    """

    def __init__(self,
                 config=dict(),
                 location=None,
                 **kwargs
                 ):
        self.logger = get_logger(self)

        # Create an object for just the mount config items
        self.mount_config = config

        self.logger.debug("Mount config: {}".format(config))
        self.config = config

        # setup commands for mount
        self.logger.debug("Setting up commands for mount")
        self.commands = self._setup_commands(kwargs.get('commands', []))
        self.logger.debug("Mount commands set up")

        # Set the initial location
        self._location = location

        # We set some initial mount properties. May come from config
        self.non_sidereal_available = self.mount_config.setdefault('non_sidereal_available', False)
        self.PEC_available = self.mount_config.setdefault('PEC_available', False)

        # Initial states
        self._is_connected = False
        self._is_initialized = False

        self._is_slewing = False
        self._is_parked = False
        self._is_tracking = False
        self._is_home = False
        self._state = 'Parked'

        self.guide_rate = 0.9  # Sidereal
        self._tracking_rate = 1.0  # Sidereal
        self._tracking = 'Sidereal'

        self._status_lookup = dict()

        # Set initial coordinates
        self._target_coordinates = None
        self._current_coordinates = None
        self._park_coordinates = None

    def connect(self):
        raise NotImplementedError()

    def status(self):
        raise NotImplementedError()

    def initialize(self):
        raise NotImplementedError()


##################################################################################################
# Properties
##################################################################################################

    @property
    def location(self):
        """ astropy.coordinates.SkyCoord: The location details for the mount.

        When a new location is set,`_setup_location_for_mount` is called, which will update the mount
        with the current location. It is anticipated the mount won't change locations while observing
        so this should only be done upon mount initialization.

        """
        return self._location

    @location.setter
    def location(self, location):
        self._location = location
        # If the location changes we need to update the mount
        self._setup_location_for_mount()

    @property
    def is_connected(self):
        """ bool: Checks the serial connection on the mount to determine if connection is open """
        return self._is_connected

    @property
    def is_initialized(self):
        """ bool: Has mount been initialied with connection """
        return self._is_initialized

    @property
    def is_parked(self):
        """ bool: Mount parked status. """
        return self._is_parked

    @property
    def is_home(self):
        """ bool: Mount home status. """
        return self._is_home

    @property
    def is_tracking(self):
        """ bool: Mount tracking status.  """
        return self._is_tracking

    @property
    def is_slewing(self):
        """ bool: Mount slewing status. """
        return self._is_slewing

    @property
    def state(self):
        """ bool: Mount state. """
        return self._state

##################################################################################################
# Methods
##################################################################################################

    def set_park_coordinates(self, ha=-170 * u.degree, dec=-10 * u.degree):
        """ Calculates the RA-Dec for the the park position.

        This method returns a location that points the optics of the unit down toward the ground.

        The RA is calculated from subtracting the desired hourangle from the local sidereal time. This requires
        a proper location be set.

        Note:
            Mounts usually don't like to track or slew below the horizon so this will most likely require a
            configuration item be set on the mount itself.

        Args:
            ha (Optional[astropy.units.degree]): Hourangle of desired parking position. Defaults to -165 degrees
            dec (Optional[astropy.units.degree]): Declination of desired parking position. Defaults to -165 degrees

        Returns:
            park_skycoord (astropy.coordinates.SkyCoord): A SkyCoord object representing current parking position.
        """
        self.logger.debug('Setting park position')

        park_time = current_time()
        park_time.location = self.location

        lst = park_time.sidereal_time('apparent')
        self.logger.debug("LST: {}".format(lst))
        self.logger.debug("HA: {}".format(ha))

        ra = lst - ha
        self.logger.debug("RA: {}".format(ra))
        self.logger.debug("Dec: {}".format(dec))

        self._park_coordinates = SkyCoord(ra, dec)

        self.logger.info("Park Coordinates RA-Dec: {}".format(self._park_coordinates))

    def get_target_coordinates(self):
        """ Gets the RA and Dec for the mount's current target. This does NOT necessarily
        reflect the current position of the mount, see `get_current_coordinates`.

        Returns:
            astropy.coordinates.SkyCoord:
        """
        return self._target_coordinates

    def set_target_coordinates(self, coords):
        """ Sets the RA and Dec for the mount's current target.

        Args:
            coords (astropy.coordinates.SkyCoord): coordinates specifying target location

        Returns:
            bool:  Boolean indicating success
        """
        self._target_coordinates = coords

    def get_current_coordinates(self):
        """ Reads out the current coordinates from the mount.

        Note:
            See `_mount_coord_to_skycoord` and `_skycoord_to_mount_coord` for translation of
            mount specific coordinates to astropy.coordinates.SkyCoord

        Returns:
            astropy.coordinates.SkyCoord
        """
        return self._current_coordinates


##################################################################################################
# Movement methods
##################################################################################################

    def slew_to_coordinates(self, coords, ra_rate=15.0, dec_rate=0.0):
        """ Slews to given coordinates.

        Note:
            Slew rates are not implemented yet.

        Args:
            coords (astropy.SkyCoord): Coordinates to slew to
            ra_rate (Optional[float]): Slew speed - RA tracking rate in arcsecond per second. Defaults to 15.0
            dec_rate (Optional[float]): Slew speed - Dec tracking rate in arcsec per second. Defaults to 0.0

        Returns:
            bool: indicating success
        """
        assert isinstance(coords, tuple), self.logger.warning(
            'slew_to_coordinates expects RA-Dec coords')

        response = 0

        if not self.is_parked:
            # Set the coordinates
            if self.set_target_coordinates(coords):
                response = self.slew_to_target()
            else:
                self.logger.warning("Could not set target_coordinates")

        return response

    def home_and_park(self):
        """ Convenience method to first slew to the home position and then park.
        """
        self.slew_to_home()
        while self.is_slewing:
            time.sleep(5)
            self.logger.info("Slewing to home, sleeping for 5 seconds")

        # Reinitialize from home seems to always do the trick of getting us to
        # correct side of pier for parking
        self._is_initialized = False
        self.initialize()
        self.park()

        while self.is_slewing:
            time.sleep(5)
            self.logger.info("Slewing to park, sleeping for 5 seconds")

        self.logger.info("Mount parked")

    def slew_to_zero(self):
        """ Calls `slew_to_home` in base class. Can be overridden.  """
        self.slew_to_home()

    def slew_to_target(self):
        """ Slews to the current _target_coordinates

        Returns:
            bool: indicating success
        """
        raise NotImplementedError()

    def slew_to_home(self):
        """ Slews the mount to the home position.

        Note:
            Home position and Park position are not the same thing

        Returns:
            bool: indicating success
        """
        raise NotImplementedError()

    def park(self):
        """ Slews to the park position and parks the mount.

        Note:
            When mount is parked no movement commands will be accepted.

        Returns:
            bool: indicating success
        """
        raise NotImplementedError()

    def unpark(self):
        """ Unparks the mount. Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """
        raise NotImplementedError()

    def move_direction(self, direction='north', seconds=1.0):
        """ Move mount in specified `direction` for given amount of `seconds`

        """
        raise NotImplementedError()

    def serial_query(self, cmd, *args):
        raise NotImplementedError()

    def serial_read(self):
        raise NotImplementedError()

    def serial_write(self, cmd):
        raise NotImplementedError()

##################################################################################################
# Private Methods
##################################################################################################

    def _setup_location_for_mount(self):
        """ Sets the current location details for the mount. """
        raise NotImplementedError()

    def _setup_commands(self, commands):
        """ Sets the current location details for the mount. """
        raise NotImplementedError()

    def _set_zero_position(self):
        """ Sets the current position as the zero (home) position. """
        raise NotImplementedError()

    def _mount_coord_to_skycoord(self):
        raise NotImplementedError()

    def _skycoord_to_mount_coord(self):
        raise NotImplementedError()
