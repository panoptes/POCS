import time
from glob import glob
from abc import abstractmethod, ABC
from contextlib import suppress
from typing import Optional, Tuple, Dict

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord
from panoptes.pocs.utils.logger import get_logger

from panoptes.utils import error
from panoptes.utils.library import load_module
from panoptes.utils.config.client import get_config
from panoptes.utils.time import current_time
from panoptes.pocs.base import PanBase
from panoptes.pocs.mount import constants
from panoptes.pocs.utils.location import create_location_from_config


class AbstractMount(PanBase, ABC):
    """
        Abstract Base class for controlling a mount. This provides the basic functionality
        for the mounts. Sub-classes should override the `initialize` method for mount-specific
        issues as well as any helper methods specific mounts might need. See
        "NotImplemented Methods" section of this module.

        Sets the following properties:

            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self._is_initialized = False

        Args:
            config (dict):              Custom configuration passed to base mount. This is usually
                                        read from the main system config.

            commands (dict):            Commands for the telescope. These are read from a yaml file
                                        that maps the mount-specific commands to common commands.

            location (EarthLocation):   An `astropy.coordinates.EarthLocation` that
                contains location information.

    """

    def __init__(self, location, commands=None, *args, **kwargs):
        super(AbstractMount, self).__init__(*args, **kwargs)

        # Create an object for just the mount config items.
        self.mount_config = self.get_config('mount')
        self.logger.debug(f'Mount config: {self.mount_config}')

        # Setup commands for mount.
        self.logger.debug('Setting up commands for mount')
        self.commands = self._setup_commands(commands)
        self.logger.debug('Mount commands set up')

        # Set the initial location
        self.location = location

        # We set some initial mount properties. May come from config
        self.non_sidereal_available = self.mount_config.setdefault('non_sidereal_available', False)
        self.pec_available = self.mount_config.setdefault('pec_available', False)

        # Initial states
        self._is_connected = False
        self._is_initialized = False

        self._is_slewing = False
        self._is_parked = True
        self._at_mount_park = True
        self._is_tracking = False
        self._is_home = False
        self._state = constants.SystemStatus.PARKED

        self.sidereal_rate = constants.MountConstants.SIDEREAL_RATE
        self._movement_speed = constants.MovementSpeedStatus.SIDEREAL_MAX
        self.tracking_mode = constants.TrackingStatus.SIDEREAL

        self.ra_guide_rate = 0.9  # Sidereal
        self.dec_guide_rate = 0.9  # Sidereal
        self._tracking_rate = 1.0  # Sidereal
        self.min_tracking_threshold = self.mount_config.get('min_tracking_threshold', 100)  # ms
        self.max_tracking_threshold = self.mount_config.get('max_tracking_threshold', 99999)  # ms

        # Set initial coordinates
        self._target_coordinates = None
        self._current_coordinates = None
        self._park_coordinates = None

    def __str__(self):
        brand = self.mount_config.get('brand', '')
        model = self.mount_config.get('model', '')
        port = ''
        with suppress(KeyError):
            port = self.mount_config['serial']['port']
        return f'{brand} {model} ({port=})'

    @property
    def status(self):
        self._update_status()
        status = {}
        try:
            status['tracking_rate'] = f'{self.tracking_rate:0.04f}'
            status['ra_guide_rate'] = self.ra_guide_rate
            status['dec_guide_rate'] = self.dec_guide_rate
            status['movement_speed'] = self.movement_speed

            current_coord = self.current_coordinates
            if current_coord is not None:
                status['current_ra'] = current_coord.ra
                status['current_dec'] = current_coord.dec

            if self.has_target:
                target_coord = self.target_coordinates
                status['mount_target_ra'] = target_coord.ra
                status['mount_target_dec'] = target_coord.dec
        except Exception as e:
            self.logger.debug(f'Problem getting mount status: {e!r}')

        return status

    @property
    def location(self):
        """The location details for the mount.

        When a new location is set,`_setup_location_for_mount` is called, which
        will update the mount with the current location. It is anticipated the
        mount won't change locations while observing so this should only be done
        upon mount initialization.
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
        """ bool: Has mount been initialised with connection """
        return self._is_initialized

    @property
    def is_parked(self):
        """ bool: Mount parked status. """
        return self._is_parked

    @property
    def at_mount_park(self):
        """ bool: True if mount is at park position. """
        return self._at_mount_park

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

    @property
    def movement_speed(self):
        """ bool: Movement speed when button pressed. """
        return self._movement_speed

    @property
    def has_target(self):
        return self._target_coordinates is not None

    @property
    def tracking_rate(self):
        """ bool: Mount tracking rate """
        return self._tracking_rate

    @tracking_rate.setter
    def tracking_rate(self, value):
        """ Set the tracking rate """
        self._tracking_rate = value

    @property
    def target_coordinates(self):
        """ Gets the RA and Dec for the mount's current target.

        This does NOT necessarily reflect the current position of the mount,
        see `get_current_coordinates`.

        Returns:
            astropy.coordinates.SkyCoord:
        """
        return self._target_coordinates

    @target_coordinates.setter
    def target_coordinates(self, new_coords):
        self._target_coordinates = new_coords

    @property
    def current_coordinates(self):
        """The current coordinates as reported by the mount."""
        return self._current_coordinates

    @current_coordinates.setter
    def current_coordinates(self, new_coords):
        self._current_coordinates = new_coords

    @property
    def distance_from_target(self):
        """ Get current distance from target.

        Returns:
            u.Angle: An angle representing the current on-sky separation from the target
        """
        target = self.target_coordinates.coord
        separation = self.current_coordinates.separation(target)
        self.logger.debug(f"Current separation from target: {separation}")

        return separation

    def disconnect(self, should_park=True):
        self.logger.info('Disconnecting mount')
        if not self.is_parked and should_park:
            self.park()

        self._is_connected = False
        self.logger.success(f'Disconnected {self}')

    def set_park_coordinates(self, ha=-170 * u.degree, dec=-10 * u.degree):
        """ Calculates the RA-Dec for the the park position.

        This method returns a location that points the optics of the unit down toward the ground.

        The RA is calculated from subtracting the desired hourangle from the
        local sidereal time. This requires a proper location be set.

        Note:
            Mounts usually don't like to track or slew below the horizon so this
                will most likely require a configuration item be set on the mount
                itself.

        Args:
            ha (Optional[astropy.units.degree]): Hourangle of desired parking
                position. Defaults to -165 degrees.
            dec (Optional[astropy.units.degree]): Declination of desired parking
                position. Defaults to -165 degrees.

        Returns:
            park_skycoord (astropy.coordinates.SkyCoord): A SkyCoord object
                representing current parking position.
        """
        self.logger.debug('Setting park position')

        park_time = current_time()
        park_time.location = self.location

        lst = park_time.sidereal_time('apparent')
        ra = lst - ha
        self.logger.debug(f'{lst=} {ha=}')
        self.logger.debug(f'{ra=} {dec=}')

        self._park_coordinates = SkyCoord(ra, dec)
        self.logger.debug(f"Park Coordinates RA-Dec: {self._park_coordinates}")

    def slew_to_coordinates(self, coords, *args, **kwargs):
        """ Slews to given coordinates.

        Note:
            Slew rates are not implemented yet.

        Args:
            coords (astropy.SkyCoord): Destination coordinates.
        Returns:
            bool: indicating success
        """
        if not isinstance(coords, SkyCoord):
            raise TypeError(f'Need astropy.coordinates.SkyCoord, got {type(coords)!r}.')
        response = 0

        if not self.is_parked:
            # Set the coordinates
            if self.set_target_coordinates(coords):
                response = self.slew_to_target(*args, **kwargs)
            else:
                self.logger.warning('Could not set target_coordinates')

        return response

    def home_and_park(self, *args, **kwargs):
        """Convenience method to first slew to the home position and then park."""
        if not self.is_parked:
            self.slew_to_home(blocking=True)

            # Reinitialize from home seems to always do the trick of getting us to
            # correct side of pier for parking
            self._is_initialized = False
            self.initialize()
            self.park(*args, **kwargs)

            while self.is_slewing and not self.is_parked:
                time.sleep(5)
                self.logger.debug('Slewing to park, sleeping for 5 seconds')

        self.logger.debug('Mount parked')

    def slew_to_zero(self, blocking=False):
        """ Calls `slew_to_home` in base class. Can be overridden.  """
        self.slew_to_home(blocking=blocking)

    def get_ms_offset(self, offset, axis='ra'):
        """ Get offset in milliseconds at current speed

        Args:
            offset (astropy.units.Angle): Offset in arcsec.
            axis (str): Which axis to move, default 'ra'.

        Returns:
             astropy.units.Quantity: Offset in milliseconds at current speed
        """

        rates = {
            'ra': self.ra_guide_rate,
            'dec': self.dec_guide_rate,
        }

        guide_rate = rates[axis]

        return (offset / (self.sidereal_rate.value * guide_rate)).to(u.ms)

    @abstractmethod
    def connect(self):
        """Connect to the mount """
        raise NotImplementedError

    @abstractmethod
    def initialize(self, *arg, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def get_tracking_correction(self,
                                offset_info: Tuple[float, float],
                                pointing_ha: float,
                                thresholds: Optional[Tuple[int, int]] = None
                                ) -> Dict[str, Tuple[float, float, str]]:
        raise NotImplementedError

    @abstractmethod
    def set_tracking_rate(self, direction='ra', delta=1.0):
        """Sets the tracking rate for the mount """
        raise NotImplementedError

    @abstractmethod
    def correct_tracking(self, correction_info, axis_timeout=30.):
        """ Make tracking adjustment corrections.

        Args:
            correction_info (dict[tuple]): Correction info to be applied, see
                `get_tracking_correction`.
            axis_timeout (float, optional): Timeout for adjustment in each axis,
                default 30 seconds.

        Raises:
            `error.Timeout`: Timeout error.
        """
        raise NotImplementedError

    @abstractmethod
    def slew_to_target(self, blocking=False, timeout=180):
        """Slews to the currently assigned target coordinates.

        Slews the mount to the coordinates that have been assigned by `set_target_coordinates`.
        If no coordinates have been set, do nothing and return `False`, otherwise
        return response from the mount.

        If `blocking=True` then wait for up to `timeout` seconds for the mount
        to reach the `is_tracking` state. If a timeout occurs, raise a `pocs.error.Timeout`
        exception.

        Args:
            blocking (bool, optional): If command should block while slewing to
                home, default False.
            timeout (int, optional): Maximum time spent slewing to home, default
                180 seconds.

        Returns:
            bool: indicating success
        """
        raise NotImplementedError

    @abstractmethod
    def slew_to_home(self, blocking=False, timeout=180):
        """Slews the mount to the home position.

        Note:
            Home position and Park position are not the same thing

        Args:
            blocking (bool, optional): If command should block while slewing to
                home, default False.
            timeout (int, optional): Maximum time spent slewing to home, default 180 seconds.

        Returns:
            bool: indicating success

        Args:
            blocking (bool, optional): If command should block while slewing to
                home, default False.
        """
        raise NotImplementedError

    @abstractmethod
    def park(self, timeout=60, *args, **kwargs):
        """ Slews to the park position and parks the mount.

        Note:
            When mount is parked no movement commands will be accepted.

        Returns:
            bool: indicating success
        """
        raise NotImplementedError

    @abstractmethod
    def unpark(self):
        """Unparks the mount.

        Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """
        raise NotImplementedError

    @abstractmethod
    def move_direction(self, direction='north', seconds=1.0):
        """Move mount in specified `direction` for given amount of `seconds`."""
        raise NotImplementedError

    @abstractmethod
    def get_current_coordinates(self):
        raise NotImplementedError

    @abstractmethod
    def set_target_coordinates(self, new_coord):
        raise NotImplementedError

    @abstractmethod
    def _setup_commands(self, commands: Optional[dict] = None):
        """Setup the mount commands."""
        raise NotImplementedError

    @abstractmethod
    def _setup_location_for_mount(self):
        """ Sets the current location details for the mount. """
        raise NotImplementedError

    @abstractmethod
    def _set_zero_position(self):
        """ Sets the current position as the zero (home) position. """
        raise NotImplementedError

    @abstractmethod
    def _get_command(self, cmd, params=None):
        raise NotImplementedError

    @abstractmethod
    def _mount_coord_to_skycoord(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def _skycoord_to_mount_coord(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def _update_status(self):
        raise NotImplementedError

    @abstractmethod
    def _set_initial_rates(self):
        raise NotImplementedError

    @classmethod
    def create_mount_from_config(cls, mount_info=None, earth_location=None,
                                 default_simulator='panoptes.pocs.mount.simulator', *args,
                                 **kwargs):
        """Create a mount instance based on the provided config.

        Creates an instance of the AbstractMount sub-class in the module specified in the config.
        Specifically, the class must be in a file called pocs/mount/<DRIVER_NAME>.py,
        and the class must be called Mount.

        Args:
            mount_info: Optional param which overrides the 'mount' entry in config if provided.
                Useful for testing.
            earth_location: `astropy.coordinates.EarthLocation` instance, representing the
                location of the mount on the Earth. If not specified, the config must include the
                observatory's location (Latitude, Longitude and Altitude above mean sea level).
                Useful for testing.
            default_simulator (str): The full name to mount simulator, default
                'panoptes.pocs.mount.simulator'.
            *args: Positional args will be passed to the concrete class specified in the config.
            **kwargs: Keyword args will be passed to the concrete class specified in the config.

        Returns:
            An instance of the Mount class if the config (or mount_info) is complete. `None` if
            neither mount_info nor config['mount'] is provided.

        Raises:
            error.MountNotFound: Exception raised when mount cannot be created
                because of incorrect configuration.
        """
        logger = get_logger()

        # If mount_info was not passed as a parameter, check config.
        if mount_info is None:
            logger.debug('No mount info provided, using values from config.')
            mount_info = get_config('mount', default=None)

            # If nothing in config, raise exception.
            if mount_info is None:
                raise error.MountNotFound('No mount information in config, cannot create.')

        # If earth_location was not passed as a parameter, check config.
        if earth_location is None:
            logger.debug('No location provided, using values from config.')

            # Get details from config.
            site_details = create_location_from_config()
            earth_location = site_details['earth_location']

        brand = mount_info.get('brand')
        driver = mount_info.get('driver')
        model = mount_info.get('model', driver)
        if not driver or not isinstance(driver, str):
            raise error.MountNotFound('Mount info in config is missing a driver name.')

        logger.debug(f'Mount: {brand=} {driver=} {model=}')

        # Check if we should be using a simulator
        use_simulator = 'mount' in get_config('simulator', default=[])
        logger.debug(f'Mount is simulator: {use_simulator}')

        # Create simulator if requested.
        if use_simulator or ('simulator' in driver):
            logger.debug(f'Creating mount simulator')
            simulator_class = load_module(default_simulator)
            return simulator_class.create_mount_simulator(mount_info=mount_info,
                                                          earth_location=earth_location)

        # See if we have a serial connection.
        try:
            port = mount_info['serial']['port']
            logger.info(f'Looking for {driver} on {port}.')
            if port is None or len(glob(port)) == 0:
                raise error.MountNotFound(msg=f'Mount {port=} not available.')
        except KeyError:
            # See Issue 866.
            if model == 'bisque':
                logger.debug('Driver specifies a bisque type mount, no serial port needed.')
            else:
                msg = 'Mount port not specified in config file. Use simulator=mount for simulator.'
                raise error.MountNotFound(msg=msg)

        logger.debug(f'Loading mount {driver=}')
        try:
            module = load_module(driver)
        except error.NotFound as e:
            raise error.MountNotFound(e)

        # Make the mount include site information.
        mount = module.Mount(location=earth_location, *args, **kwargs)

        logger.success(f'{driver} mount created')

        return mount
