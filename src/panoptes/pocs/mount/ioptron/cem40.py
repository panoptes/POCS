import re
import time

from astropy import units as u
from astropy.time import Time

from panoptes.pocs.mount.ioptron.base import Mount as BaseMount
from panoptes.pocs.mount.ioptron import MountState


class Mount(BaseMount):
    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, location, mount_version='0040', *args, **kwargs):
        self._mount_version = mount_version
        super(Mount, self).__init__(location, *args, **kwargs)
        self.logger.success('iOptron CEM40 mount created')

    def search_for_home(self):
        """Search for the home position.

        This method uses the internal homing pin on the CEM40 mount to return the
        mount to the home (or zero) position.
        """
        self.logger.info('Searching for the home position.')
        self.query('search_for_home')
        while self.status.get('state') != MountState.AT_HOME:
            self.logger.trace(f'Searching for home position.')
            time.sleep(1)

    def _update_status(self):
        status = super()._update_status()

        # Get and parse the time from the mount.
        ts = status['timestamp']
        offset = status['time_offset']

        try:
            now = int(ts[5:]) * u.ms
            j2000 = Time(2000, format='jyear')
            t0 = j2000 + now + offset

            status['time_local'] = t0.iso
        except Exception:
            pass

        return status
