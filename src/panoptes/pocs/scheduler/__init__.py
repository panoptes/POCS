import os

from astropy import units as u

from panoptes.pocs.scheduler.constraint import Altitude
from panoptes.pocs.scheduler.constraint import Duration
from panoptes.pocs.scheduler.constraint import MoonAvoidance

# Below is needed for import
from panoptes.pocs.scheduler.scheduler import BaseScheduler  # pragma: no flakes
from panoptes.utils import error
from panoptes.utils import horizon as horizon_utils
from panoptes.utils.library import load_module
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config

from panoptes.pocs.utils.location import create_location_from_config


def create_scheduler_from_config(config_port=6563, observer=None, *args, **kwargs):
    """ Sets up the scheduler that will be used by the observatory """

    logger = get_logger()

    scheduler_config = get_config('scheduler', default=None, port=config_port)
    logger.info(f'scheduler_config: {scheduler_config!r}')

    if scheduler_config is None or len(scheduler_config) == 0:
        logger.info("No scheduler in config")
        return None

    if not observer:
        logger.debug(f'No Observer provided, creating from config.')
        site_details = create_location_from_config(config_port=config_port)
        observer = site_details['observer']

    scheduler_type = scheduler_config.get('type', 'dispatch')

    # Read the targets from the file
    fields_file = scheduler_config.get('fields_file', 'simple.yaml')
    fields_path = os.path.join(get_config('directories.targets', port=config_port), fields_file)
    logger.debug('Creating scheduler: {}'.format(fields_path))

    if os.path.exists(fields_path):

        try:
            # Load the required module
            module = load_module(f'panoptes.pocs.scheduler.{scheduler_type}')

            obstruction_list = get_config('location.obstructions', default=[], port=config_port)
            default_horizon = get_config(
                'location.horizon', default=30 * u.degree, port=config_port)

            horizon_line = horizon_utils.Horizon(
                obstructions=obstruction_list,
                default_horizon=default_horizon.value
            )

            # Simple constraint for now
            constraints = [
                Altitude(horizon=horizon_line, config_port=config_port),
                MoonAvoidance(config_port=config_port),
                Duration(default_horizon, weight=5., config_port=config_port)
            ]

            # Create the Scheduler instance
            scheduler = module.Scheduler(observer,
                                         fields_file=fields_path,
                                         constraints=constraints,
                                         config_port=config_port)
            logger.debug("Scheduler created")
        except error.NotFound as e:
            raise error.NotFound(msg=e)
    else:
        raise error.NotFound(
            msg="Fields file does not exist: {}".format(fields_file))

    return scheduler
