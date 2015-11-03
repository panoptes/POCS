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
        config['init_commands'] = {}

        super().__init__(config)

        # Set the initial location
        self._location = location

        self._setup_location_for_mount()

        # Set some initial commands
        self.config['init_commands'].update({
            'TELESCOPE_SLEW_RATE': {'SLEW_MAX': 'On'},
            'GUIDE_RATE': {'GUIDE_RATE': '0.90'},
            'DEVICE_PORT': {'PORT': config['port']},
        })

        # We set some initial mount properties. May come from config
        # self.non_sidereal_available = self.mount_config.setdefault('non_sidereal_available', False)
        # self.PEC_available = self.mount_config.setdefault('PEC_available', False)

        # Initial states
        self.is_initialized = False
        self._is_parked = False
        self._is_slewing = False
        self._is_parking = False
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
        self._is_parked = False
        if self.get_property('TELESCOPE_PARK', '_STATE', result=True) == 'Ok':
            self._is_parked = True

        return self._is_parked

    @property
    def is_home(self):
        """ bool: Mount home status. """
        self._is_home = False
        self.logger.warning("is_home ISN'T WORKING RIGHT. DON'T TRUST RESULT")
        if self.get_property('HOME', '_STATE', result=True) == 'Ok':
            self._is_home = True

        return self._is_home

    @property
    def is_parking(self):
        """ bool: Mount parked status. """
        self._is_parking = False
        if self.get_property('TELESCOPE_PARK', '_STATE', result=True) == 'Busy':
            self._is_parking = True

        return self._is_parking

    @property
    def is_slewing(self):
        """ bool: Mount tracking status.  """
        self._is_slewing = False
        if self.get_property('EQUATORIAL_EOD_COORD', '_STATE', result=True) == 'Busy':
            self._is_slewing = True

        return self._is_slewing

    @property
    def is_tracking(self):
        """ bool: Mount slewing status. """
        self._is_tracking = False
        if self.get_property('TELESCOPE_TRACK_RATE', '_STATE', result=True) == 'Busy':
            self._is_tracking = True

        return self._is_tracking

##################################################################################################
# Methods
##################################################################################################

    def status(self):
        """ Gets the system status

        """
        pass

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
        # Save the skycoord coordinates
        self._target_coordinates = coords

    def get_current_coordinates(self):
        """ Reads out the current coordinates from the mount.

        Note:
            See `_mount_coord_to_skycoord` and `_skycoord_to_mount_coord` for translation of
            mount specific coordinates to astropy.coordinates.SkyCoord

        Returns:
            astropy.coordinates.SkyCoord
        """
        self.logger.debug('Getting current mount coordinates')

        dec = self.get_property('EQUATORIAL_EOD_COORD', 'DEC', result=True)
        ra = self.get_property('EQUATORIAL_EOD_COORD', 'RA', result=True)

        # Turn the mount coordinates into a SkyCoord
        self._current_coordinates = SkyCoord(ra=float(ra) * u.degree, dec=float(dec) * u.degree)

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

        self.set_property('TELESCOPE_PARK_POSITION', {
            'PARK_DEC': '{:2.05f}'.format(dec.value),
            'PARK_RA': ':2.05f'.format(ra.value)
        })

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

            ra = self._target_coordinates.ra
            dec = self._target_coordinates.dec

            self.logger.debug("Setting RA/Dec: {} {}".format(ra.value, dec.value))

            self.set_property('TIME_UTC', {
                'UTC': Time.now().isot.split('.')[0],
                'OFFSET': '{}'.format(self.config.get('utc_offset'))
            })
            self.set_property('ON_COORD_SET', {'SLEW': 'Off', 'SYNC': 'Off', 'TRACK': 'On'})
            self.set_property(
                'EQUATORIAL_EOD_COORD', {
                    'RA': '{:2.05f}'.format(ra.to(u.hourangle).value),
                    'DEC': '{:2.02f}'.format(dec.value)
                })

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
        self.set_target_coordinates(self._park_coordinates)
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
        """ Slew to the home position and then slew to park """

        self.slew_to_home()
        while self.is_slewing:
            time.sleep(5)
            self.logger.info("Slewing to home, sleeping for 5 seconds")

        # INDI driver is parking once it gets to home setting.
        self.unpark()
        self.park()

        while self.is_slewing:
            time.sleep(5)
            self.logger.info("Slewing to park, sleeping for 5 seconds")

        if self.is_parked:
            self.logger.info("Mount parked")
        else:
            self.logger.error("MOUNT DID NOT PARK CORRECTLY")

    def move_direction(self, direction='north', seconds=1.0):
        """ Move mount in specified `direction` for given amount of `seconds`

        Args:
            direction(str):     Direction to move mount. One of four cardinal directions, defaults to 'north'.
            seconds(float):     Number of seconds to sleep, defaults to 1.0
        """
        seconds = float(seconds)
        assert direction in ['north', 'south', 'east', 'west']

        if direction in ['north', 'south']:
            move_command = 'TELESCOPE_MOTION_NS'
        else:
            move_command = 'TELESCOPE_MOTION_WE'

        self.logger.debug("Move command: {}".format(move_command))

        try:
            self.set_property(move_command, {'MOTION_{}'.format(direction.upper()): 'On'})
            time.sleep(seconds)
            self.set_property(move_command, {'MOTION_{}'.format(direction.upper()): 'Off'})
        except Exception as e:
            self.logger.warning("Problem moving command!! Make sure mount has stopped moving: {}".format(e))
        finally:
            # Note: We do this twice. That's fine.
            self.logger.debug("Stopping movement")
            self.set_property("TELESCOPE_ABORT_MOTION", {'ABORT': 'On'})


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
        * Universal Time Offset set_gmt_offset
        * Current Date set_local_date
        * Current Time set_local_time
        """

        # East longitude for mount
        lon = (360 + self.location.longitude.to(u.degree).value) % 360

        self.config['init_commands'].update({
            'TIME_UTC': {
                'UTC': Time.now().isot.split('.')[0],
                'OFFSET': '{}'.format(self.config.get('utc_offset'))
            },
            'GEOGRAPHIC_COORD': {
                'LAT': "{:2.02f}".format(self.location.latitude.to(u.degree).value),
                'LONG': "{:2.02f}".format(lon),
                'ELEV': "{:.0f}".format(self.location.height.value),
            },
        })

    def _sync_coords(self, coords):
        """ Sync mount to given coordinates

        Note:
            Here be dragons.

        Args:
            corods(SkyCoord):   Coordinates to sync to
        """
        self.logger.debug("Sync coordinates to {}".format(coords))
        self.set_property('ON_COORD_SET', {'SLEW': 'Off', 'SYNC': 'On', 'TRACK': 'Off'})

        ra = coords.ra
        dec = coords.dec

        self.set_property(
            'EQUATORIAL_EOD_COORD', {
                'RA': '{:2.05f}'.format(ra.to(u.hourangle).value),
                'DEC': '{:2.02f}'.format(dec.value)
            })
        self.set_property('ON_COORD_SET', {'SLEW': 'Off', 'SYNC': 'Off', 'TRACK': 'On'})

##################################################################################################
# NotImplemented Methods - child class
##################################################################################################
