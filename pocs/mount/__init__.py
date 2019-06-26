from glob import glob

from pocs.mount.mount import AbstractMount  # pragma: no flakes
from pocs.utils import error
from pocs.utils import load_module
from pocs.utils.location import create_location_from_config
from pocs.utils.logger import get_root_logger


def create_mount_from_config(config, mount_info=None, earth_location=None):
    """ Sets up the mount that will be used by the observatory """

    logger = get_root_logger()

    if 'mount' not in config:
        logger.info("No mount information in config, cannot create.")
        return None

    if earth_location is None:
        logger.debug(f'No location provided, using values from config.')
        site_details = create_location_from_config(config)
        earth_location = site_details['earth_location']

    if mount_info is None:
        logger.debug(f'No mount info provided, using values from config.')
        mount_info = config.get('mount')

    model = mount_info.get('model')

    driver = mount_info.get('driver')

    # See if we have a serial connection
    try:
        port = mount_info['serial']['port']
        if port is None or len(glob(port)) == 0:
            msg = "Mount port({}) not available. ".format(port) + "Use simulator = mount for simulator. Exiting."
            raise error.MountNotFound(msg=msg)
    except KeyError:
        # TODO(jamessynge): We should move the driver specific validation into the driver
        # module (e.g. module.create_mount_from_config). This means we have to adjust the
        # definition of this method to return a validated but not fully initialized mount
        # driver.
        if model != 'bisque':
            msg = "No port specified for mount in config file. Use simulator = mount for simulator. Exiting."
            raise error.MountNotFound(msg=msg)

    logger.debug('Creating mount: {}'.format(model))

    module = load_module('pocs.mount.{}'.format(driver))

    # Make the mount include site information
    mount = module.Mount(location=earth_location)

    logger.debug('Mount created')

    return mount
