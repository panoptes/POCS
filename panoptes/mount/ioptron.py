import re

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
        self._ra_format = re.compile(
            '(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})')
        self._dec_format = re.compile(
            '(?P<sign>[\+\-])(?P<degree>\d{2})\*(?P<minute>\d{2}):(?P<second>\d{2})')
        self.logger.info('Mount created')


    def initialize(self):
        """
        iOptron mounts are initialized by sending the following two commands
        to the mount:
        * Version
        * MountInfo

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
                self.serial_query('calibrate_mount')

        self.logger.info('Mount initialized: {}'.format(self.is_initialized))

        self.setup_site()

        return self.is_initialized


    def _mount_coord_to_skycoord(self, mount_ra, mount_dec):
        """
        Converts between iOptron RA/Dec format and a SkyCoord

        @param  mount_ra    RA in mount specific format
        @param  mount_dec   Dec in mount specific format

        @retval     astropy.coordinates.SkyCoord
        """
        ra_match = self._ra_format.fullmatch(mount_ra)
        dec_match = self._dec_format.fullmatch(mount_dec)

        coords = None

        if ra_match is not None and dec_match is not None:
            ra = "{}h{}m{}s".format(
                ra_match.group('hour'),
                ra_match.group('minute'),
                ra_match.group('second')
            )
            dec = "{}{}d{}m{}s".format(
                dec_match.group('sign'),
                dec_match.group('degree'),
                dec_match.group('minute'),
                dec_match.group('second')
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
        mount_ra = "{:=02.0f}:{:=02.0f}:{:=02.0f}".format(ra_hms.h, ra_hms.m, ra_hms.s)

        dec_dms = coords.dec.dms
        mount_dec = "{:=+03.0f}*{:02.0f}:{:02.0f}".format(dec_dms.d, abs(dec_dms.m), abs(dec_dms.s))

        mount_coords = (mount_ra, mount_dec)

        return mount_coords
