import re

from astropy.time import Time

from panoptes.pocs.mount.ioptron.base import Mount as BaseMount


class Mount(BaseMount):
    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, location, mount_version='0030', *args, **kwargs):
        self._mount_version = mount_version
        super(Mount, self).__init__(location, *args, **kwargs)
        self.logger.info('Creating iOptron iEQ30Pro mount')

        self._coords_format = re.compile(
            r'(?P<ra_millisecond>\d{8})' +
            r'(?P<dec_sign>[\+\-])(?P<dec_arcsec>\d{8})'
        )

        self._latitude_format = '{:+07.0f}'
        self._longitude_format = '{:+07.0f}'

        self._status_format = re.compile(
            r'(?P<longitude>[+\-]\d{6})' +
            r'(?P<latitude>\d{6})' +
            r'(?P<gps>[0-2])' +
            r'(?P<state>[0-7])' +
            r'(?P<tracking>[0-4])' +
            r'(?P<movement_speed>[1-9])' +
            r'(?P<time_source>[1-3])' +
            r'(?P<hemisphere>[01])'
        )

        self.logger.success('iOptron iEQ30Pro Mount created')

    def _update_status(self):
        status = super()._update_status()

        # Get and parse the time from the mount.
        ts = status['timestamp']

        status['time_local'] = Time(f'{ts[6:]}').iso

        return status
