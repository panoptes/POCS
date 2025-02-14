from panoptes.pocs.mount.ioptron.cem40 import Mount as BaseMount


class Mount(BaseMount):

    def __init__(self, location, mount_version='0012', *args, **kwargs):
        self._mount_version = mount_version
        super(Mount, self).__init__(location, *args, **kwargs)
        self.logger.success('iOptron HAE16 mount created')
