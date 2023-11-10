import time

from panoptes.pocs.mount.ioptron import MountState
from panoptes.pocs.mount.ioptron.base import Mount as BaseMount


class Mount(BaseMount):
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
