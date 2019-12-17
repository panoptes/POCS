from glob import glob

from pocs.mount.mount import AbstractMount  # pragma: no flakes
from pocs.utils.config import load_config
from pocs.utils import error
from pocs.utils import load_module
from pocs.utils.location import create_location_from_config
from pocs.utils.logger import get_root_logger


def create_mount_from_config(config=None,
                             mount_info=None,
                             earth_location=None,
                             logger=None,
                             *args, **kwargs):
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
        logger (`logging`|None, optional): A python logging instance.
        *args: Other positional args will be passed to the concrete class specified in the config.
        **kwargs: Other keyword args will be passed to the concrete class specified in the config.

    Returns:
        An instance of the Mount class if the config (or mount_info) is complete. `None` if neither
        mount_info nor config['mount'] is provided.

    Raises:
        error.MountNotFound: Exception raised when mount cannot be created
            because of incorrect configuration.
    """
    if logger is None:
        logger = get_root_logger()

    if not config:
        config = load_config(**kwargs)

    # If mount_info was not passed as a paramter, check config.
    if mount_info is None:
        logger.debug('No mount info provided, using values from config.')
        try:
            mount_info = config['mount']
        except KeyError:
            raise error.MountNotFound('No mount information in config, cannot create.')

    # If earth_location was not passed as a paramter, check config.
    if earth_location is None:
        logger.debug('No location provided, using values from config.')

        # Get detail from config.
        site_details = create_location_from_config(config)
        earth_location = site_details['earth_location']

    driver = mount_info.get('driver')
    if not driver or not isinstance(driver, str):
        raise error.MountNotFound('Mount info in config is missing a driver name.')

    model = mount_info.get('model', driver)
    logger.debug(f'Mount: driver={driver} model={model}')

    if driver != 'simulator':
        # See if we have a serial connection
        try:
            port = mount_info['serial']['port']
            logger.debug(f'Looking for mount {driver} on {port}.')
            if port is None or len(glob(port)) == 0:
                msg = f'Mount port ({port}) not available. Use simulator = mount for simulator.'
                raise error.MountNotFound(msg=msg)
        except KeyError:
            # Note: see Issue #866
            if driver == 'bisque':
                logger.debug(f'Driver specifies a bisque mount type, no serial port needed.')
            else:
                msg = 'Mount port not specified in config file. Use simulator=mount for simulator.'
                raise error.MountNotFound(msg=msg)

    logger.debug(f'Loading mount driver: pocs.mount.{driver}')

    try:
        module = load_module('pocs.mount.{}'.format(driver))
    except error.NotFound as e:
        raise error.MountNotFound(e)

    # Make the mount include site information
    mount = module.Mount(config=config, location=earth_location, *args, **kwargs)

    logger.info(f'{driver} mount created')

    return mount
