import re

from astropy import units as u
from astropy.coordinates import SkyCoord

from panoptes.mount.mount_serial import AbstractSerialMount

from ..utils.config import load_config
from ..utils import error as error
from ..utils import current_time


class Mount(AbstractSerialMount):

    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.info('Creating iOptron mount')

        self.config = load_config()

        # Regexp to match the iOptron RA/Dec format
        self._ra_format = '(?P<ra_millisecond>\d{8})'
        self._dec_format = '(?P<dec_sign>[\+\-])(?P<dec_arcsec>\d{8})'
        self._coords_format = re.compile(self._dec_format + self._ra_format)

        self._raw_status = None
        self._status_format = re.compile(
            '(?P<gps>[0-2]{1})' +
            '(?P<state>[0-7]{1})' +
            '(?P<tracking>[0-4]{1})' +
            '(?P<movement_speed>[1-9]{1})' +
            '(?P<time_source>[1-3]{1})' +
            '(?P<hemisphere>[01]{1})'
        )

        self._status_lookup = {
            'gps': {
                '0': 'Off',
                '1': 'On',
                '2': 'Data Extracted'
            },
            'state': {
                '0': 'Stopped - Not at Zero Position',
                '1': 'Tracking (PEC disabled)',
                '2': 'Slewing',
                '3': 'Guiding',
                '4': 'Meridian Flipping',
                '5': 'Tracking (PEC enabled)',
                '6': 'Parked',
                '7': 'Stopped - Zero Position'
            },
            'tracking': {
                '0': 'Sidereal',
                '1': 'Lunar',
                '2': 'Solar',
                '3': 'King',
                '4': 'Custom'
            },
            'movement_speed': {
                '1': '1x sidereal',
                '2': '2x sidereal',
                '3': '8x sidereal',
                '4': '16x sidereal',
                '5': '64x sidereal',
                '6': '128x sidereal',
                '7': '256x sidereal',
                '8': '512x sidereal',
                '9': 'Max sidereal',
            },
            'time_source': {
                '1': 'RS-232',
                '2': 'Hand Controller',
                '3': 'GPS'
            },
            'hemisphere': {
                '0': 'Southern',
                '1': 'Northern'
            }
        }

        self.logger.info('Mount created')


##################################################################################################
# Properties
##################################################################################################

    @property
    def is_parked(self):
        """ bool: Mount parked status. """
        self._is_parked = 'Parked' in self.status().get('state', '')

        return self._is_parked

    @property
    def is_home(self):
        """ bool: Mount home status. """
        self._is_home = 'Stopped - Zero Position' in self.status().get('state', '')

        return self._is_home

    @property
    def is_tracking(self):
        """ bool: Mount tracking status. """
        self._is_tracking = 'Tracking' in self.status().get('state', '')

        return self._is_tracking

    @property
    def is_slewing(self):
        """ bool: Mount slewing status. """
        self._is_slewing = 'Slewing' in self.status().get('state', '')

        return self._is_slewing


##################################################################################################
# Public Methods
##################################################################################################

    def initialize(self):
        """ Initialize the connection with the mount and setup for location.

        iOptron mounts are initialized by sending the following two commands
        to the mount:

        * Version
        * MountInfo

        If the mount is successfully initialized, the `_setup_location_for_mount` method
        is also called.

        Returns:
            bool:   Returns the value from `self.is_initialized`.
        """
        if not self.is_connected:
            self.logger.info('Connecting to mount {}'.format(__name__))
            self.connect()

        if self.is_connected and not self.is_initialized:
            self.logger.info('Initializing {} mount'.format(__name__))

            # We trick the mount into thinking it's initialized while we
            # initialize otherwise the `serial_query` method will test
            # to see if initialized and be put into loop.
            self._is_initialized = True

            actual_version = self.serial_query('version')
            actual_mount_info = self.serial_query('mount_info')

            expected_version = self.commands.get('version').get('response')
            expected_mount_info = "{:04d}".format(self.mount_config.get('model', 30))
            self._is_initialized = False

            # Test our init procedure for iOptron
            if actual_version != expected_version or actual_mount_info != expected_mount_info:
                self.logger.debug('{} != {}'.format(actual_version, expected_version))
                self.logger.debug('{} != {}'.format(actual_mount_info, expected_mount_info))
                raise error.MountNotFound('Problem initializing mount')
            else:
                self._is_initialized = True
                self._setup_location_for_mount()

        self.logger.info('Mount initialized: {}'.format(self.is_initialized))

        return self.is_initialized


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
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')
        assert self.location is not None, self.logger.warning('Please set a location before attempting setup')

        self.logger.info('Setting up mount for location')

        # Location
        # Adjust the lat/long for format expected by iOptron
        lat = '{:+07.0f}'.format(self.location.latitude.to(u.arcsecond).value)
        lon = '{:+07.0f}'.format(self.location.longitude.to(u.arcsecond).value)

        self.serial_query('set_long', lon)
        self.serial_query('set_lat', lat)

        # Time
        self.serial_query('disable_daylight_savings')

        gmt_offset = self.config.get('location').get('gmt_offset', 0)
        self.serial_query('set_gmt_offset', gmt_offset)

        now = current_time() + gmt_offset * u.minute

        self.serial_query('set_local_time', now.datetime.strftime("%H%M%S"))
        self.serial_query('set_local_date', now.datetime.strftime("%y%m%d"))

        # Make sure we start at sidereal
        self.set_tracking_rate()

        self.serial_query('set_guide_rate', '090')
        self.guide_rate = float(self.serial_query('get_guide_rate')) / 100.0
        self.logger.debug("Mount guide rate: {}".format(self.serial_query('get_guide_rate')))
        self.logger.debug("Mount guide rate: {}".format(self.guide_rate))

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

        # self.logger.debug("Mount coordinates: {}".format(coords_match))

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
        # self.logger.debug("RA (ms): {}".format(ra_ms))

        dec_dms = (coords.dec.degree * u.degree).to(u.centiarcsecond)
        # self.logger.debug("Dec (centiarcsec): {}".format(dec_dms))
        mount_dec = "{:=+08.0f}".format(dec_dms.value)

        mount_coords = (mount_ra, mount_dec)

        return mount_coords

    def _set_zero_position(self):
        """ Sets the current position as the zero position.

        The iOptron allows you to set the current position directly, so
        we simply call the iOptron command.
        """
        self.logger.info("Setting zero position")
        return self.serial_query('set_zero_position')
