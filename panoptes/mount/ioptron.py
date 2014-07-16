import re

from panoptes.mount.mount import AbstractMount
import panoptes.utils.logger as logger
import panoptes.utils.error as error


@logger.set_log_level('debug')
@logger.has_logger
class Mount(AbstractMount):

    """
    iOptron mounts
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._ra_format = re.compile(
            '(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})')
        self._dec_format = re.compile(
            '(?P<sign>[\+\-])(?P<degree>\d{2})\*(?P<minute>\d{2}):(?P<second>\d{2})')

    def initialize_mount(self):
        """
            iOptron init procedure:
                    - Version
                    - MountInfo
        """
        self.logger.info('Initializing {} mount'.format(__name__))
        if not self.is_connected:
            self.connect()

        if not self.is_initialized:

            # We trick the mount into thinking it's initialized while we
            # initialize
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

        self.serial_query('set_guide_rate', '050')

        self.logger.debug('Mount initialized: {}'.format(self.is_initialized))
        return self.is_initialized

    def _mount_coord_to_skycoord(self, mount_ra, mount_dec):
        ra_match = self._ra_format.fullmatch(mount_ra)
        dec_match = self._dec_format.fullmatch(mount_dec)

        c = None

        if ra_match is not None and dec_match is not None:
            ra = "{}h{}m{}s".format(
                ra_match.group('hour'), ra_match.group('minute'), ra_match.group('second'))
            dec = "{}{}d{}m{}s".format(dec_match.group('sign'), dec_match.group(
                'hour'), dec_match.group('minute'), dec_match.group('second'))
            c = SkyCoord(ra, dec, frame='icrs')
        else:
            self.logger.warning(
                "Cannot create SkyCoord from mount coordinates")

        return c
