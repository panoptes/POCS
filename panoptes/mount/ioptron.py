import re
import ephem

from astropy import units as u
from astropy.coordinates import SkyCoord

from panoptes.mount.mount import AbstractMount
from panoptes.utils import logger, config, param_server, error

@logger.set_log_level('debug')
@logger.has_logger
class Mount(AbstractMount):

    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, *args, **kwargs):
        self.logger.info('Creating mount')
        super().__init__(*args, **kwargs)

        # Regexp to match the iOptron RA/Dec format
        self._ra_format = re.compile('(?P<ra_hour>\d{2})(?P<ra_minute>\d{2})(?P<ra_second>\d{2})')
        self._dec_format = re.compile('(?P<dec_sign>[\+\-])(?P<dec_degree>\d{2})(?P<dec_minute>\d{2})(?P<dec_second>\d{2})')
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
        if not self.is_connected():
            self.connect()

        if not self.is_initialized:

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
                self.logger.debug(
                    '{} != {}'.format(actual_version, expected_version))
                self.logger.debug(
                    '{} != {}'.format(actual_mount_info, expected_mount_info))
                raise error.MountNotFound('Problem initializing mount')
            else:
                self.is_initialized = True
                self.setup_site()

        self.logger.info('Mount initialized: {}'.format(self.is_initialized))

        return self.is_initialized

    def setup_site(self, site=None):
        """
        Sets the mount up to the current site. Includes:
        * Latitude set_long
        * Longitude set_lat
        * Universal Time Offset set_gmt_offset
        * Daylight Savings disable_daylight_savings
        * Current Date set_local_date
        * Current Time set_local_time

        Args:
            site (ephem.Observer): A defined location for the observatory.
        """
        site = self.site
        assert site is not None, self.logger.warning('setup_site requires a site in the config')
        self.logger.info('Setting up mount for site')

        # Location
            # Adjust the lat/long for format expected by iOptron
        lat = '{}'.format(site.lat).replace(':', '').split('.')[0]
        lon = '{}'.format(site.long).replace(':', '').split('.')[0]

        if site.lat > 0:
            lat = '+{}'.format(lat)
        else:
            lat = '-{}'.format(lat)

        if site.lon > 0:
            lon = '+{}'.format(lon)
        else:
            lon = '-{}'.format(lon)

        self.serial_query('set_long', lon)
        self.serial_query('set_lat', lat)

        # Time
        self.serial_query('disable_daylight_savings')
        self.serial_query('set_gmt_offset', self.config.get('site').get('gmt_offset', 0))

        dt = ephem.localtime(site.date)

        t = "{:02d}{:02d}{:02d}".format(dt.hour, dt.minute, dt.second)
        d = "{:02d}{:02d}{:02d}".format(dt.year - 2000, dt.month, dt.day)

        self.serial_query('set_local_time', t)
        self.serial_query('set_local_date', d)


    def _mount_coord_to_skycoord(self, mount_coords):
        """
        Converts between iOptron RA/Dec format and a SkyCoord

        @param  mount_ra    RA in mount specific format
        @param  mount_dec   Dec in mount specific format

        @retval     astropy.coordinates.SkyCoord
        """
        coords_match = self._coords_format.fullmatch(mount_coords)

        coords = None

        if coords_match is not None:
            ra = "{}h{}m{}s".format(
                coords_match.group('ra_hour'),
                coords_match.group('ra_minute'),
                coords_match.group('ra_second')
            )
            dec = "{}{}d{}m{}s".format(
                coords_match.group('dec_sign'),
                coords_match.group('dec_degree'),
                coords_match.group('dec_minute'),
                coords_match.group('dec_second')
            )
            coords = SkyCoord(ra, dec, frame='icrs')
        else:
            self.logger.warning(
                "Cannot create SkyCoord from mount coordinates")

        return coords


    def _skycoord_to_mount_coord(self, coords):
        """
        Converts between SkyCoord and a iOptron RA/Dec format

        @param  coords  astropy.coordinates.SkyCoord

        @retval         A tuple of RA/Dec coordinates
        """

        ra_hms = coords.ra.hms
        mount_ra = "{:=02.0f}1{:=02.0f}{:=02.0f}".format(ra_hms.h, ra_hms.m, ra_hms.s)

        dec_dms = coords.dec.dms
        mount_dec = "{:=+03.0f}{:02.0f}{:02.0f}".format(dec_dms.d, abs(dec_dms.m), abs(dec_dms.s))

        mount_coords = (mount_ra, mount_dec)

        return mount_coords
