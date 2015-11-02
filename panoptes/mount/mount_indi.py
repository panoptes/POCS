import time

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

from ..utils import has_logger
from ..utils.indi import PanIndiDevice


@has_logger
class Mount(PanIndiDevice):

    def __init__(self,
                 config=dict(),
                 location=None,
                 ):
        """
        Abstract Base class for controlling a mount. This provides the basic functionality
        for the mounts. Sub-classes should override the `initialize` method for mount-specific
        issues as well as any helper methods specific mounts might need. See "NotImplemented Methods"
        section of this module.

        Sets the following properies:

            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self.is_initialized = False

        Args:
            config (dict):              Custom configuration passed to base mount. This is usually
                                        read from the main system config.

            commands (dict):            Commands for the telescope. These are read from a yaml file
                                        that maps the mount-specific commands to common commands.

            location (EarthLocation):   An astropy.coordinates.EarthLocation that contains location information.
        """
        config['driver'] = 'indi_ieq_telescope'

        super().__init__(config)

        # Set the initial location
        self._location = location

        self._setup_location_for_mount()

        # We set some initial mount properties. May come from config
        # self.non_sidereal_available = self.mount_config.setdefault('non_sidereal_available', False)
        # self.PEC_available = self.mount_config.setdefault('PEC_available', False)

        # Initial states
        self.is_initialized = False
        self._is_slewing = False
        self._is_parked = False
        self._is_tracking = False
        self._is_home = False

        self._status_lookup = dict()

        # Set initial coordinates
        self._target_coordinates = None
        self._current_coordinates = None
        self._park_coordinates = None

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
    def is_parked(self):
        """ bool: Mount parked status. """
        raise NotImplementedError

    @property
    def is_home(self):
        """ bool: Mount home status. """
        raise NotImplementedError

    @property
    def is_tracking(self):
        """ bool: Mount tracking status.  """
        raise NotImplementedError

    @property
    def is_slewing(self):
        """ bool: Mount slewing status. """
        raise NotImplementedError

##################################################################################################
# Methods
##################################################################################################

    def initialize(self):
        raise NotImplementedError

    def status(self):
        """
        Gets the system status

        Note:
            From the documentation (iOptron ® Mount RS-232 Command Language 2014 Version 2.0 August 8th, 2014)

            Command: “:GAS#”
            Response: “nnnnnn#”

            See `self._status_lookup` for more information.

        Returns:
            dict:   Translated output from the mount
        """
        # Get the status
        self._raw_status = self.serial_query('get_status')

        status_match = self._status_format.fullmatch(self._raw_status)
        status = status_match.groupdict()

        # Lookup the text values and replace in status dict
        for k, v in status.items():
            status[k] = self._status_lookup[k][v]

        return status

    def get_target_coordinates(self):
        """ Gets the RA and Dec for the mount's current target. This does NOT necessarily
        reflect the current position of the mount, see `get_current_coordinates`.

        Returns:
            astropy.coordinates.SkyCoord:
        """

        if self._target_coordinates is None:
            self.logger.info("Target coordinates not set")
        else:
            self.logger.info('Mount target_coordinates: {}'.format(self._target_coordinates))

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
        self._target_coordinates = coords

        # Get coordinate format from mount specific class
        mount_coords = self._skycoord_to_mount_coord(self._target_coordinates)

        # Send coordinates to mount
        try:
            self.serial_query('set_ra', mount_coords[0])
            self.serial_query('set_dec', mount_coords[1])
            target_set = True
        except:
            self.logger.warning("Problem setting mount coordinates")

        return target_set

    def get_current_coordinates(self):
        """ Reads out the current coordinates from the mount.

        Note:
            See `_mount_coord_to_skycoord` and `_skycoord_to_mount_coord` for translation of
            mount specific coordinates to astropy.coordinates.SkyCoord

        Returns:
            astropy.coordinates.SkyCoord
        """
        self.logger.debug('Getting current mount coordinates')

        mount_coords = self.serial_query('get_coordinates')

        # Turn the mount coordinates into a SkyCoord
        self._current_coordinates = self._mount_coord_to_skycoord(mount_coords)

        return self._current_coordinates

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

        park_time = Time.now()
        park_time.location = self.location

        lst = park_time.sidereal_time('apparent')
        self.logger.debug("LST: {}".format(lst))
        self.logger.debug("HA: {}".format(ha))

        ra = lst - ha
        self.logger.debug("RA: {}".format(ra))
        self.logger.debug("Dec: {}".format(dec))

        self._park_coordinates = SkyCoord(ra, dec)

        self.logger.info("Park Coordinates RA-Dec: {}".format(self._park_coordinates))

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

    def slew_to_target(self):
        """ Slews to the current _target_coordinates

        Returns:
            bool: indicating success
        """
        response = 0

        if not self.is_parked:
            assert self._target_coordinates is not None, self.logger.warning(
                "Target Coordinates not set")

            response = self.serial_query('slew_to_target')
            self.logger.debug("Mount response: {}".format(response))
            if response:
                self.logger.debug('Slewing to target')
            else:
                self.logger.warning('Problem with slew_to_target')
        else:
            self.logger.info('Mount is parked')

        return response

    def slew_to_home(self):
        """ Slews the mount to the home position.

        Note:
            Home position and Park position are not the same thing

        Returns:
            bool: indicating success
        """
        self.set_property('HOME', {'GoToHome': 'On'})

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
        if self.set_property('TELESCOPE_PARK', {'PARK': 'On'}) == 0:
            self.logger.debug('Slewing to park')
        else:
            self.logger.warning('Problem with slew_to_park')

    def unpark(self):
        """ Unparks the mount. Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """
        if self.set_property('TELESCOPE_PARK', {'UNPARK': 'On'}) == 0:
            self.logger.info('Mount unparked')
        else:
            self.logger.warning('Problem with unpark')

    def home_and_park(self):

        self.slew_to_home()
        while self.is_slewing:
            time.sleep(5)
            self.logger.info("Slewing to home, sleeping for 5 seconds")

        # Reinitialize from home seems to always do the trick of getting us to
        # correct side of pier for parking
        self.is_initialized = False
        self.initialize()
        self.park()

        while self.is_slewing:
            time.sleep(5)
            self.logger.info("Slewing to park, sleeping for 5 seconds")

        self.logger.info("Mount parked")

    def move_direction(self, direction='north', seconds=1.0):
        """ Move mount in specified `direction` for given amount of `seconds`

        """
        seconds = float(seconds)
        assert direction in ['north', 'south', 'east', 'west']

        move_command = 'move_{}'.format(direction)
        self.logger.debug("Move command: {}".format(move_command))

        try:
            now = Time.now()
            self.logger.debug("Moving {} for {} seconds. ".format(direction, seconds))
            self.serial_query(move_command)

            time.sleep(seconds)

            self.logger.debug("{} seconds passed before stop".format(Time.now() - now))
            self.serial_query('stop_moving')
            self.logger.debug("{} seconds passed total".format(Time.now() - now))
        except Exception as e:
            self.logger.warning("Problem moving command!! Make sure mount has stopped moving: {}".format(e))
        finally:
            # Note: We do this twice. That's fine.
            self.logger.debug("Stopping movement")
            self.serial_query('stop_moving')


##################################################################################################
# Private Methods
##################################################################################################

    def _setup_location_for_mount(self):
        """
        Sets the mount up to the current location. Mount must be initialized first.

        This uses mount.location (an astropy.coords.EarthLocation) to set most of the params and the rest is
        read from a config file.  Users should not call this directly.

        Includes:
        * Latitude set_long
        * Longitude set_lat
        * Daylight Savings disable_daylight_savings
        * Universal Time Offset set_gmt_offset
        * Current Date set_local_date
        * Current Time set_local_time


        """

        self.config['init_commands'] = {
            'TIME_UTC': {
                'UTC': Time.now().isot.split('.')[0],
                'OFFSET': '-10.00'
            },
            'GEOGRAPHIC_COORD': {
                'LAT': self.location.latitude.to(u.degree).value,
                'LONG': self.location.longitude.to(u.degree).value,
                'ELEV': '3400',
            },
        }


##################################################################################################
# NotImplemented Methods - child class
##################################################################################################

    def _set_zero_position(self):
        """ Sets the current position as the zero (home) position. """
        raise NotImplementedError

    def _mount_coord_to_skycoord(self, mount_coords):
        """
        Converts between iOptron RA/Dec format and a SkyCoord

        Args:
            mount_coords (str): Coordinates as returned by mount

        Returns:
            astropy.SkyCoord:   Mount coordinates as astropy SkyCoord with
                EarthLocation included.
        """
        coords_match = self._coords_format.fullmatch(mount_coords)

        coords = None

        self.logger.info("Mount coordinates: {}".format(coords_match))

        if coords_match is not None:
            ra = (coords_match.group('ra_millisecond') * u.millisecond).to(u.hour)
            dec = (coords_match.group('dec_arcsec') * u.centiarcsecond).to(u.arcsec)

            dec_sign = coords_match.group('dec_sign')
            if dec_sign == '-':
                dec = dec * -1

            coords = SkyCoord(ra=ra, dec=dec, frame='icrs', unit=(u.hour, u.arcsecond))
        else:
            self.logger.warning(
                "Cannot create SkyCoord from mount coordinates")

        return coords

    def _skycoord_to_mount_coord(self, coords):
        """
        Converts between SkyCoord and a iOptron RA/Dec format.

            `
            TTTTTTTT(T) 0.01 arc-seconds
            XXXXX(XXX) milliseconds

            Command: “:SrXXXXXXXX#”
            Defines the commanded right ascension, RA. Slew, calibrate and park commands operate on the
            most recently defined right ascension.

            Command: “:SdsTTTTTTTT#”
            Defines the commanded declination, Dec. Slew, calibrate and park commands operate on the most
            recently defined declination.
            `

        @param  coords  astropy.coordinates.SkyCoord

        @retval         A tuple of RA/Dec coordinates
        """

        # RA in milliseconds
        ra_ms = (coords.ra.hour * u.hour).to(u.millisecond)
        mount_ra = "{:08.0f}".format(ra_ms.value)
        self.logger.debug("RA (ms): {}".format(ra_ms))

        dec_dms = (coords.dec.degree * u.degree).to(u.centiarcsecond)
        self.logger.debug("Dec (centiarcsec): {}".format(dec_dms))
        mount_dec = "{:=+08.0f}".format(dec_dms.value)

        mount_coords = (mount_ra, mount_dec)

        return mount_coords
