from contextlib import suppress
from glob import glob

from panoptes.pocs.mount.mount import AbstractMount  # pragma: no flakes
from panoptes.pocs.utils.location import create_location_from_config
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils import error
from panoptes.utils.library import load_module
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config

logger = get_logger()


def create_mount_from_config(config_port='6563',
                             mount_info=None,
                             earth_location=None,
                             *args, **kwargs):
    """Create a mount instance based on the provided config.

    Creates an instance of the AbstractMount sub-class in the module specified in the config.
    Specifically, the class must be in a file called pocs/mount/<DRIVER_NAME>.py,
    and the class must be called Mount.

    Args:
        config_port: The port number of the config server, default 6563.
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
        error.MountNotFound: Exception raised when mount cannot be created
            because of incorrect configuration.
    """

    # If mount_info was not passed as a parameter, check config.
    if mount_info is None:
        logger.debug('No mount info provided, using values from config.')
        mount_info = get_config('mount', default=None, port=config_port)

        # If nothing in config, raise exception.
        if mount_info is None:
            raise error.MountNotFound('No mount information in config, cannot create.')

    # If earth_location was not passed as a parameter, check config.
    if earth_location is None:
        logger.debug('No location provided, using values from config.')

        # Get details from config.
        site_details = create_location_from_config(config_port=config_port)
        earth_location = site_details['earth_location']

    driver = mount_info.get('driver')
    if not driver or not isinstance(driver, str):
        raise error.MountNotFound('Mount info in config is missing a driver name.')

    model = mount_info.get('model', driver)
    logger.debug(f'Mount: driver={driver} model={model}')

    # Check if we should be using a simulator
    use_simulator = 'mount' in get_config('simulator', default=[], port=config_port)
    logger.debug(f'Mount is simulator: {use_simulator}')

    # Create simulator if requested
    if use_simulator or (driver == 'simulator'):
        logger.debug(f'Creating mount simulator')
        return create_mount_simulator()

    # See if we have a serial connection
    try:
        port = mount_info['serial']['port']
        logger.info(f'Looking for {driver} on {port}.')
        if port is None or len(glob(port)) == 0:
            msg = f'Mount port ({port}) not available. Use simulator = mount for simulator.'
            raise error.MountNotFound(msg=msg)
    except KeyError:
        # See Issue 866
        if model == 'bisque':
            logger.debug('Driver specifies a bisque type mount, no serial port needed.')
        else:
            msg = 'Mount port not specified in config file. Use simulator=mount for simulator.'
            raise error.MountNotFound(msg=msg)

    logger.debug(f'Loading mount driver: pocs.mount.{driver}')
    try:
        module = load_module(f'panoptes.pocs.mount.{driver}')
    except error.NotFound as e:
        raise error.MountNotFound(e)

    # Make the mount include site information
    mount = module.Mount(config_port=config_port, location=earth_location, *args, **kwargs)

    logger.success(f'{driver} mount created')

    return mount


def create_mount_simulator(config_port='6563', *args, **kwargs):
    # Remove mount simulator
    current_simulators = get_config('simulator', default=[], port=config_port)
    logger.warning(f'Current simulators: {current_simulators}')
    with suppress(ValueError):
        current_simulators.remove('mount')

    mount_config = {
        'model': 'simulator',
        'driver': 'simulator',
        'serial': {
            'port': 'simulator'
        }
    }

    # Set mount device info to simulator
    set_config('mount', mount_config, port=config_port)

    earth_location = create_location_from_config(config_port=config_port)['earth_location']

    logger.debug(f"Loading mount driver: pocs.mount.{mount_config['driver']}")
    try:
        module = load_module(f"panoptes.pocs.mount.{mount_config['driver']}")
    except error.NotFound as e:
        raise error.MountNotFound(f'Error loading mount module: {e!r}')

    mount = module.Mount(location=earth_location, config_port=config_port, *args, **kwargs)

    logger.success(f"{mount_config['driver']} mount created")

    return mount
