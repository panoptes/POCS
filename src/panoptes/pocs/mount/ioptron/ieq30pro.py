"""iOptron iEQ30Pro mount wrapper leveraging the shared iOptron base."""

from panoptes.pocs.mount.ioptron.base import Mount as BaseMount


class Mount(BaseMount):
    """iOptron iEQ30Pro model-specific Mount wrapper."""

    def __init__(self, location, mount_version="0030", *args, **kwargs):
        self._mount_version = mount_version
        super(Mount, self).__init__(location, *args, **kwargs)
        self.logger.success("iOptron iEQ30Pro Mount created")
