"""iOptron HAE16 mount wrapper reusing the CEM40 base behavior."""

from panoptes.pocs.mount.ioptron.cem40 import Mount as BaseMount


class Mount(BaseMount):
    """iOptron HAE16 model-specific Mount shim.

    Simply sets the expected mount_version and otherwise relies on BaseMount/CEM40
    behavior.
    """

    def __init__(self, location, mount_version="0012", *args, **kwargs):
        super(Mount, self).__init__(location, mount_version=mount_version, *args, **kwargs)
