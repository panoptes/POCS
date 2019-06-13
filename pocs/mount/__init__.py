from glob import glob

from pocs.mount.mount import AbstractMount  # pragma: no flakes
from pocs.utils import error
from pocs.utils import load_module
from pocs.utils.logger import get_root_logger


def create_mount_from_config(config, mount_info=None, earth_location=None, ignore_local_config=False, simulator=None):
    """Creates a mount object.

     Details for the creation of the mount object are held in the
     configuration file or can be passed to the method.

     This method ensures that the proper mount type is loaded.

     Args:
         mount_info (dict):  Configuration items for the mount.

     Returns:
         pocs.mount:     Returns a sub-class of the mount type
     """

    logger = get_root_logger()

    if 'mount' not in config:
        logger.info("No mount in config")
        return None

    if not earth_location:
        logger.info("No valid site information")
        return None

    if mount_info is None:
        mount_info = config.get('mount')

    model = mount_info.get('model')

    if 'mount' in config.get('simulator', []):
        model = 'simulator'
        driver = 'simulator'
        mount_info['simulator'] = True
    else:
        model = mount_info.get('brand')
        driver = mount_info.get('driver')

        # See if we have a serial connection
        try:
            port = mount_info['serial']['port']
            if port is None or len(glob(port)) == 0:
                msg = "Mount port({}) not available. ".format(port) \
                      + "Use simulator = mount for simulator. Exiting."
                raise error.MountNotFound(msg=msg)
        except KeyError:
            # TODO(jamessynge): We should move the driver specific validation into the driver
            # module (e.g. module.create_mount_from_config). This means we have to adjust the
            # definition of this method to return a validated but not fully initialized mount
            # driver.
            if model != 'bisque':
                msg = "No port specified for mount in config file. " \
                      + "Use simulator = mount for simulator. Exiting."
                raise error.MountNotFound(msg=msg)

    logger.debug('Creating mount: {}'.format(model))

    module = load_module('pocs.mount.{}'.format(driver))

    # Make the mount include site information
    mount = module.Mount(location=earth_location)

    logger.debug('Mount created')

    return mount
