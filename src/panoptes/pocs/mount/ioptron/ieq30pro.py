from panoptes.pocs.mount.ioptron.base import Mount as BaseMount


class Mount(BaseMount):
    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, location, mount_version='0030', *args, **kwargs):
        self._mount_version = mount_version
        super(Mount, self).__init__(location, *args, **kwargs)
        self.logger.success('iOptron iEQ30Pro Mount created')

    def search_for_home(self):
        """Search for the home position not supported."""
        self.logger.warning('Searching for home position not supported iEQ30Pro.'
                            'Please set the home position manually via the hand-controller.')
