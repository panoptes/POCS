from panoptes.pocs.mount.ioptron.cem40 import Mount as BaseMount


class Mount(BaseMount):

    def __init__(self, location, mount_version='0012', *args, **kwargs):
        super(Mount, self).__init__(location, mount_version=mount_version, *args, **kwargs)
        self.logger.success('iOptron HAE16 mount created')
