import re

from astropy import units as u
from astropy.coordinates import SkyCoord

from panoptes.mount.mount import AbstractMount

from ..utils.logger import has_logger
from ..utils.config import load_config

@has_logger
class Mount(AbstractMount):

    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, *args, **kwargs):
        self.logger.info('Creating iOptron mount')
        super().__init__(*args, **kwargs)

        self.config = load_config()

        # Regexp to match the iOptron RA/Dec format
        self._ra_format = '(?P<ra_millisecond>\d{8})'
        self._dec_format = '(?P<dec_sign>[\+\-])(?P<dec_arcsec>\d{8})'
        self._coords_format = re.compile(self._dec_format + self._ra_format)

        self.logger.info('Mount created')

    def initialize(self):
        """
        iOptron mounts are initialized by sending the following two commands
        to the mount:
        * Version
        * MountInfo

        If the mount is successfully initialized, the `calibrate_mount` command
        is also issued to the mount.

        Returns:
            bool:   Returns the value from `self.is_initialized`.
        """
        self.logger.info('Initializing {} mount'.format(__name__))
        if not self.is_connected:
            self.connect()

        if self.is_connected and not self.is_initialized:

            # We trick the mount into thinking it's initialized while we
            # initialize otherwise the `serial_query` method will test
            # to see if initialized and be put into loop.
            self.is_initialized = True

            actual_version = self.serial_query('version')
            actual_mount_info = self.serial_query('mount_info')

            expected_version = self.commands.get('version').get('response')
            expected_mount_info = self.commands.get(
                'mount_info').get('response')
            self.is_initialized = False

            # Test our init procedure for iOptron
            if actual_version != expected_version or actual_mount_info != expected_mount_info:
                self.logger.debug( '{} != {}'.format(actual_version, expected_version))
                self.logger.debug( '{} != {}'.format(actual_mount_info, expected_mount_info))
                raise error.MountNotFound('Problem initializing mount')
            else:
                self.is_initialized = True
                self._setup_site_for_mount()

        self.logger.info('Mount initialized: {}'.format(self.is_initialized))

        return self.is_initialized

    def status(self):
        """
        Gets the system status

        From the documentation (iOptron ® Mount RS-232 Command Language 2014 Version 2.0 August 8th, 2014)

        Command: “:GAS#”
        Response: “nnnnnn#”
        The 1st digit stands for GPS status: 0 means GPS off, 1 means GPS on, 2 means GPS data extracted
        correctly.
        The 2nd digit stands for system status: 0 means stopped (not at zero position), 1 means tracking
        with PEC disabled, 2 means slewing, 3 means guiding, 4 means meridian flipping, 5 means tracking
        with PEC enabled (only for non-encoder edition), 6 means parked, 7 means stopped at zero position
        (home position).
        The 3rd digit stands for tracking rates: 0 means sidereal rate, 1 means lunar rate, 2 means solar rate,
        3 means King rate, 4 means custom rate.
        The 4th digit stands for moving speed by arrow button or moving command: 1 means 1x sidereal
        tracking rate, 2 means 2x, 3 means 8x, 4 means 16x, 5 means 64x, 6 means 128x, 7 means 256x, 8
        means 512x, 9 means maximum speed. Currently, the maximum speed of CEM60 (-EC) is 900x,
        the maximum speed of iEQ45 Pro (/AA) is 1400x.
        The 5th digit stands for time source: 1 means RS-232 port, 2 means hand controller, 3 means GPS.
        The 6th digit stands for hemisphere: 0 means Southern Hemisphere, 1 means Northern Hemisphere.
        """
        # Get the status
        status_raw = self.serial_query('get_status')

        self._status_format = re.compile(
            '(?P<gps>[0-2]{1})' +
            '(?P<system>[0-7]{1})' +
            '(?P<tracking>[0-4]{1})' +
            '(?P<movement_speed>[1-9]{1})' +
            '(?P<time_source>[1-3]{1})' +
            '(?P<hemisphere>[01]{1})'
        )

        status_match = self._status_format.fullmatch(status_raw)
        status = status_match.groupdict()

        status_lookup = {
            'gps':    {
                '0': 'Off',
                '1': 'On',
                '2': 'Data Extracted'
            },
            'system':   {
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

        # Lookup the text values and replace in status dict
        for k, v in status.items():
            status[k] = status_lookup[k][v]

        return status

    def _setup_site_for_mount(self):
        """
        Sets the mount up to the current site. Mount must be initialized first.

        This uses mount.site (an astropy.coords.EarthLocation) to set most of the params and the rest is
        read from a config file.  Users should not call this directly but instead call `set_site`, which
        exists in the base class.

        Includes:
        * Latitude set_long
        * Longitude set_lat
        * Universal Time Offset set_gmt_offset
        * Daylight Savings disable_daylight_savings
        * Current Date set_local_date
        * Current Time set_local_time


        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        assert self.site is not None, self.logger.warning('Please set a site before attempting setup')
        self.logger.info('Setting up mount for site')

        # Location
        # Adjust the lat/long for format expected by iOptron
        lat = '{:+07.0f}'.format(self.site.latitude.to(u.arcsecond))
        lon = '{:+07.0f}'.format(self.site.longitude.to(u.arcsecond))

        self.serial_query('set_long', lon)
        self.serial_query('set_lat', lat)

        # Time
        self.serial_query('disable_daylight_savings')
        self.serial_query('set_gmt_offset', self.config.get('site').get('gmt_offset', 0))

        now = Time.now()

        self.serial_query('set_local_time', now.datetime.strftime("%H%M%s"))
        self.serial_query('set_local_date', now.datetime.strftime("%y%m%d"))

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

        dec_dms = (coords.dec.degree * u.degree).to(u.centiarcsecond)
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

    def _set_park_position(self):
        """ Sets the current position as the park position.

        This will read the current coordinates and then update the config file.
        Future calls to _park_coordinates will use this position.
        """
        self.logger.info("Setting park position")

        coords = self.get_current_coordinates()
