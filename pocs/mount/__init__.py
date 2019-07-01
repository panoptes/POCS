from glob import glob

from pocs.mount.mount import AbstractMount  # pragma: no flakes
from pocs.utils import error
from pocs.utils import load_module
from pocs.utils.location import create_location_from_config
from pocs.utils.logger import get_root_logger


def create_mount_from_config(config, mount_info=None, earth_location=None, *args, **kwargs):
    """Create a mount instance based on the provided config.

    Creates an instance of the AbstractMount sub-class in the module specified in the config.
    Specifically, the class must be in a file called pocs/mount/<DRIVER_NAME>.py,
    and the class must be called Mount.

    Args:
        config: A dictionary of name to value, as produced by `panoptes.utils.config.load_config`.
        mount_info: Optional param which overrides the 'mount' entry in config if provided.
            Useful for testing.
        earth_location: `astropy.coordinates.EarthLocation` instance, representing the
            location of the mount on the Earth. If not specified, the config must include the
            observatory's location (Latitude, Longitude and Altitude above mean sea level).
            Useful for testing.
        *args: Other positional args will be passed to the concrete class specified in the config.
        **kwargs: Other keyword args will be passed to the concrete class specified in the config.

    Returns:
        An instance of the Mount class if the config (or mount_info) is complete. `None` if neither
        mount_info nor config['mount'] is provided.

    Raises:
        `error.MountNotFound`: Missing the serial.port info for a mount which requires it (i.e. not
            a Software Bisque mount).
    """
    logger = get_root_logger()

    if mount_info is None:
        logger.debug('No mount info provided, using values from config.')
        mount_info = config.get('mount')
        if 'mount' not in config:
            logger.info("No mount information in config, cannot create.")
            return None

    if earth_location is None:
        logger.debug('No location provided, using values from config.')
        site_details = create_location_from_config(config)
        earth_location = site_details['earth_location']

    driver = mount_info.get('driver')
    if not driver or not isinstance(driver, str):
        raise error.MountNotFound('Mount info in config is missing a driver name.')

    model = mount_info.get('model', driver)

    # See if we have a serial connection
    try:
        port = mount_info['serial']['port']
        if port is None or len(glob(port)) == 0:
            msg = f'Mount port ({port}) not available. Use simulator = mount for simulator.'
            raise error.MountNotFound(msg=msg)
    except KeyError:
        if model != 'bisque':
            msg = 'No port specified for mount in config file. Use simulator = mount for simulator. '
            raise error.MountNotFound(msg=msg)

    logger.debug('Creating mount: {}'.format(model))

    module = load_module('pocs.mount.{}'.format(driver))

    # Make the mount include site information
    mount = module.Mount(location=earth_location, *args, **kwargs)

    logger.info(f'{driver} mount created')

    return mount
