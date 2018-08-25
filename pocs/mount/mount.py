import time

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord

from pocs.base import PanBase

from pocs.utils import current_time
from pocs.utils import error


class AbstractMount(PanBase):

    """
        Abstract Base class for controlling a mount. This provides the basic functionality
        for the mounts. Sub-classes should override the `initialize` method for mount-specific
        issues as well as any helper methods specific mounts might need. See
        "NotImplemented Methods" section of this module.

        Sets the following properies:

            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self._is_initialized = False

        Args:
            config (dict):              Custom configuration passed to base mount. This is usually
                                        read from the main system config.

            commands (dict):            Commands for the telescope. These are read from a yaml file
                                        that maps the mount-specific commands to common commands.

            location (EarthLocation):   An astropy.coordinates.EarthLocation that
                contains location information.

    """

    def __init__(self, location, commands=None, *args, **kwargs
                 ):
        super(AbstractMount, self).__init__(*args, **kwargs)
        assert isinstance(location, EarthLocation)

        # Create an object for just the mount config items
        self.mount_config = self.config.get('mount')

        self.logger.debug("Mount config: {}".format(self.mount_config))

        # setup commands for mount
        self.logger.debug("Setting up commands for mount")
        if commands is None:
            commands = dict()
        self.commands = self._setup_commands(commands)
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
        self._is_parked = True
        self._at_mount_park = True
        self._is_tracking = False
        self._is_home = False
        self._state = 'Parked'

        self.sidereal_rate = ((360 * u.degree).to(u.arcsec) / (86164 * u.second))
        self.ra_guide_rate = 0.9  # Sidereal
        self.dec_guide_rate = 0.9  # Sidereal
        self._tracking_rate = 1.0  # Sidereal
        self._tracking = 'Sidereal'
        self._movement_speed = ''

        self._status_lookup = dict()

        # Set initial coordinates
        self._target_coordinates = None
        self._current_coordinates = None
        self._park_coordinates = None

    def connect(self):  # pragma: no cover
        raise NotImplementedError

    def disconnect(self):
        self.logger.info('Connecting to mount')
        if not self.is_parked:
            self.park()

        self._is_connected = False

    def status(self):
        status = {}
        try:
            status['tracking_rate'] = '{:0.04f}'.format(self.tracking_rate)
            status['ra_guide_rate'] = self.ra_guide_rate
            status['dec_guide_rate'] = self.dec_guide_rate
            status['movement_speed'] = self.movement_speed

            current_coord = self.get_current_coordinates()
            if current_coord is not None:
                status['current_ra'] = current_coord.ra
                status['current_dec'] = current_coord.dec

            if self.has_target:
                target_coord = self.get_target_coordinates()
                status['mount_target_ra'] = target_coord.ra
                status['mount_target_dec'] = target_coord.dec
        except Exception as e:
            self.logger.debug('Problem getting mount status: {}'.format(e))

        status.update(self._update_status())
        return status

    def initialize(self, *arg, **kwargs):  # pragma: no cover
        raise NotImplementedError


##################################################################################################
# Properties
##################################################################################################

    @property
    def location(self):
        """ astropy.coordinates.SkyCoord: The location details for the mount.

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

##################################################################################################
# Methods
##################################################################################################

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
        self.logger.debug("LST: {}".format(lst))
        self.logger.debug("HA: {}".format(ha))

        ra = lst - ha
        self.logger.debug("RA: {}".format(ra))
        self.logger.debug("Dec: {}".format(dec))

        self._park_coordinates = SkyCoord(ra, dec)

        self.logger.debug("Park Coordinates RA-Dec: {}".format(self._park_coordinates))

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
        target_set = False

        # Save the skycoord coordinates
        self.logger.debug("Setting target coordinates: {}".format(coords))
        self._target_coordinates = coords

        # Get coordinate format from mount specific class
        mount_coords = self._skycoord_to_mount_coord(self._target_coordinates)

        # Send coordinates to mount
        try:
            self.query('set_ra', mount_coords[0])
            self.query('set_dec', mount_coords[1])
            target_set = True
        except Exception as e:
            self.logger.warning("Problem setting mount coordinates: {} {}".format(mount_coords, e))

        return target_set

    def get_current_coordinates(self):
        """ Reads out the current coordinates from the mount.

        Note:
            See `_mount_coord_to_skycoord` and `_skycoord_to_mount_coord` for translation of
            mount specific coordinates to astropy.coordinates.SkyCoord

        Returns:
            astropy.coordinates.SkyCoord
        """
        # self.logger.debug('Getting current mount coordinates')

        mount_coords = self.query('get_coordinates')

        # Turn the mount coordinates into a SkyCoord
        self._current_coordinates = self._mount_coord_to_skycoord(mount_coords)

        return self._current_coordinates

    def distance_from_target(self):
        """ Get current distance from target

        Returns:
            u.Angle: An angle represeting the current on-sky separation from the target
        """
        target = self.get_target_coordinates().coord
        separation = self.get_current_coordinates().separation(target)

        self.logger.debug("Current separation from target: {}".format(separation))

        return separation

    def get_tracking_correction(self, offset_info, pointing_ha):
        """Determine the needed tracking corrections from current position.

        This method will determine the direction and number of milliseconds to
        correct the mount for each axis in order to correct for any tracking
        drift. The Declination axis correction ('north' or 'south') depends on
        the movement of the camera box with respect to the pier, which can be
        determined from the Hour Angle (HA) of the pointing image in the sequence.

        Note:
            Correction values below 50ms will be skipped and values above 99999ms
            will be clipped.

        Args:
            offset_info (`OffsetError`): A named tuple describing the offset
                error. See `pocs.images.OffsetError`.
            pointing_ha (float): The Hour Angle (HA) of the mount at the
                beginning of the observation sequence in degrees. This affects
                the direction of the Dec adjustment.

        Returns:
            dict: Offset corrections for each axis as needed ::

                dict: {
                    # axis: (arcsec, millisecond, direction)
                    'ra': (float, float, str),
                    'dec': (float, float, str),
                }
        """
        pier_side = 'east'
        if pointing_ha <= 12:
            pier_side = 'west'

        self.logger.debug("Mount pier side: {}".format(pier_side))

        axis_corrections = {
            'dec': None,
            'ra': None,
        }

        for axis in axis_corrections.keys():
            # find the number of ms and direction for Dec axis
            offset = getattr(offset_info, 'delta_{}'.format(axis))
            offset_ms = self.get_ms_offset(offset, axis=axis)

            if axis == 'dec':
                # Determine which direction to move based on direction mount
                # is moving (i.e. what side it started on).
                if pier_side == 'east':
                    if offset_ms >= 0:
                        delta_direction = 'north'
                    else:
                        delta_direction = 'south'
                else:
                    if offset_ms >= 0:
                        delta_direction = 'south'
                    else:
                        delta_direction = 'north'
            else:
                if offset_ms >= 0:
                    delta_direction = 'west'
                else:
                    delta_direction = 'east'

            offset_ms = abs(offset_ms.value)

            # Skip short corrections
            if offset_ms <= 50:
                continue

            # Ensure we don't try to move for too long
            max_time = 99999

            # Correct long offset
            if offset_ms > max_time:
                offset_ms = max_time

            axis_corrections[axis] = (offset, offset_ms, delta_direction)

        return axis_corrections

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
        for axis, corrections in correction_info.items():
            offset = corrections[0]
            offset_ms = corrections[1]
            delta_direction = corrections[2]

            self.logger.info("Adjusting {}: {} {:0.2f} ms {:0.2f}".format(
                axis, delta_direction, offset_ms, offset))

            self.mount.query(
                'move_ms_{}'.format(delta_direction),
                '{:05.0f}'.format(offset_ms)
            )

            # Adjust tracking for `axis_timeout` seconds then fail if not done.
            start_tracking_time = current_time()
            while self.mount.is_tracking is False:
                if (current_time() - start_tracking_time).sec > axis_timeout:
                    raise error.Timeout("Tracking adjustment timeout: {}".format(axis))

                self.logger.debug("Waiting for {} tracking adjustment".format(axis))
                time.sleep(0.5)


##################################################################################################
# Movement methods
##################################################################################################

    def slew_to_coordinates(self, coords, ra_rate=15.0, dec_rate=0.0):
        """ Slews to given coordinates.

        Note:
            Slew rates are not implemented yet.

        Args:
            coords (astropy.SkyCoord): Coordinates to slew to
            ra_rate (Optional[float]): Slew speed - RA tracking rate in
                arcsecond per second. Defaults to 15.0
            dec_rate (Optional[float]): Slew speed - Dec tracking rate in
                arcsec per second. Defaults to 0.0

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
        if not self.is_parked:
            self.slew_to_home()
            while self.is_slewing:
                time.sleep(5)
                self.logger.debug("Slewing to home, sleeping for 5 seconds")

            # Reinitialize from home seems to always do the trick of getting us to
            # correct side of pier for parking
            self._is_initialized = False
            self.initialize()
            self.park()

            while self.is_slewing and not self.is_parked:
                time.sleep(5)
                self.logger.debug("Slewing to park, sleeping for 5 seconds")

        self.logger.debug("Mount parked")

    def slew_to_target(self):
        """ Slews to the current _target_coordinates

        Args:
            on_finish(method):  A callback method to be executed when mount has
            arrived at destination

        Returns:
            bool: indicating success
        """
        success = False

        if self.is_parked:
            self.logger.info("Mount is parked")
        elif not self.has_target:
            self.logger.info("Target Coordinates not set")
        else:
            success = self.query('slew_to_target')

            self.logger.debug("Mount response: {}".format(success))
            if success:
                self.logger.debug('Slewing to target')

            else:
                self.logger.warning('Problem with slew_to_target')

        return success

    def slew_to_home(self):
        """ Slews the mount to the home position.

        Note:
            Home position and Park position are not the same thing

        Returns:
            bool: indicating success
        """
        response = 0

        if not self.is_parked:
            self._target_coordinates = None
            response = self.query('slew_to_home')
        else:
            self.logger.info('Mount is parked')

        return response

    def slew_to_zero(self):
        """ Calls `slew_to_home` in base class. Can be overridden.  """
        self.slew_to_home()

    def park(self):
        """ Slews to the park position and parks the mount.

        Note:
            When mount is parked no movement commands will be accepted.

        Returns:
            bool: indicating success
        """

        self.set_park_coordinates()
        self.set_target_coordinates(self._park_coordinates)

        response = self.query('park')

        if response:
            self.logger.debug('Slewing to park')
        else:
            self.logger.warning('Problem with slew_to_park')

        while not self._at_mount_park:
            self.status()
            time.sleep(2)

        self._is_parked = True

        return response

    def unpark(self):
        """ Unparks the mount. Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """

        response = self.query('unpark')

        if response:
            self._is_parked = False
            self.logger.debug('Mount unparked')
        else:
            self.logger.warning('Problem with unpark')

        return response

    def move_direction(self, direction='north', seconds=1.0):
        """ Move mount in specified `direction` for given amount of `seconds`

        """
        seconds = float(seconds)
        assert direction in ['north', 'south', 'east', 'west']

        move_command = 'move_{}'.format(direction)
        self.logger.debug("Move command: {}".format(move_command))

        try:
            now = current_time()
            self.logger.debug("Moving {} for {} seconds. ".format(direction, seconds))
            self.query(move_command)

            time.sleep(seconds)

            self.logger.debug("{} seconds passed before stop".format((current_time() - now).sec))
            self.query('stop_moving')
            self.logger.debug("{} seconds passed total".format((current_time() - now).sec))
        except KeyboardInterrupt:
            self.logger.warning("Keyboard interrupt, stopping movement.")
        except Exception as e:
            self.logger.warning(
                "Problem moving command!! Make sure mount has stopped moving: {}".format(e))
        finally:
            # Note: We do this twice. That's fine.
            self.logger.debug("Stopping movement")
            self.query('stop_moving')

    def set_tracking_rate(self, direction='ra', delta=1.0):
        """Sets the tracking rate for the mount """
        raise NotImplementedError

    def get_ms_offset(self, offset, axis='ra'):
        """ Get offset in milliseconds at current speed

        Args:
            offset (astropy.units.Angle): Offset in arcseconds

        Returns:
             astropy.units.Quantity: Offset in milliseconds at current speed
        """

        rates = {
            'ra': self.ra_guide_rate,
            'dec': self.dec_guide_rate,
        }

        guide_rate = rates[axis]

        return (offset / (self.sidereal_rate * guide_rate)).to(u.ms)

    def query(self, cmd, params=None):
        """Sends a query to the mount and returns response.

        Performs a send and then returns response. Will do a translate on cmd first. This should
        be the major serial utility for commands. Accepts an additional args that is passed
        along with the command. Checks for and only accepts one args param.

        Args:
            cmd (str): A command to send to the mount. This should be one of the
                commands listed in the mount commands yaml file.
            params (str, optional): Params to pass to serial connection

        Examples:
            >>> mount.query('set_local_time', '101503')  #doctest: +SKIP
            '1'
            >>> mount.query('get_local_time')            #doctest: +SKIP
            '101503'

        Returns:
            bool: indicating success

        Deleted Parameters:
            *args: Parameters to be sent with command if required.
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        full_command = self._get_command(cmd, params=params)
        self.write(full_command)

        response = self.read()

        # expected_response = self._get_expected_response(cmd)
        # if str(response) != str(expected_response):
        #     self.logger.warning("Expected: {}\tGot: {}".format(expected_response, response))

        return response

    def write(self, cmd):
        raise NotImplementedError

    def read(self, *args):
        raise NotImplementedError

##################################################################################################
# Private Methods
##################################################################################################

    def _get_expected_response(self, cmd):
        """ Looks up appropriate response for command for telescope """
        # self.logger.debug('Mount Response Lookup: {}'.format(cmd))

        response = ''

        # Get the actual command
        cmd_info = self.commands.get(cmd)

        if cmd_info is not None:
            response = cmd_info.get('response')
            # self.logger.debug('Mount Command Response: {}'.format(response))
        else:
            raise error.InvalidMountCommand(
                'No result for command {}'.format(cmd))

        return response

    def _setup_location_for_mount(self):  # pragma: no cover
        """ Sets the current location details for the mount. """
        raise NotImplementedError

    def _setup_commands(self, commands):  # pragma: no cover
        """ Sets the current location details for the mount. """
        raise NotImplementedError

    def _set_zero_position(self):  # pragma: no cover
        """ Sets the current position as the zero (home) position. """
        raise NotImplementedError

    def _get_command(self, cmd, params=None):  # pragma: no cover
        raise NotImplementedError

    def _mount_coord_to_skycoord(self):  # pragma: no cover
        raise NotImplementedError

    def _skycoord_to_mount_coord(self):  # pragma: no cover
        raise NotImplementedError

    def _update_status(self):  # pragma: no cover
        return {}
