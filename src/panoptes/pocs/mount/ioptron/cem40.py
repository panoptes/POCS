import time

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
        while self.is_home is False:
            time.sleep(1)
            self.update_status()

    def set_target_coordinates(self, *args, **kwargs):
        """After setting target coordinates, check number of positions.

        The CEM40 can determine if there are 0, 1, or 2 possible positions
        for the given RA/Dec, with the latter being the case for the meridian
        flip.
        """
        target_set = super().set_target_coordinates(*args, **kwargs)
        self.logger.debug(f'Checking number of possible positions for {self._target_coordinates}')
        num_possible_positions = self.query('query_positions')
        self.logger.debug(f'Number of possible positions: {num_possible_positions}')

        if num_possible_positions == 0:
            self.logger.warning(f'No possible positions for {self._target_coordinates}')
            return False

        # There is currently a bug with with the CEM40 where it will reset the
        # target coordinates after querying the number of possible positions so
        # we need to set them again.
        target_set = super().set_target_coordinates(*args, **kwargs)

        return target_set
