import os

from astropy import units as u

from pocs.scheduler.constraint import Altitude
from pocs.scheduler.constraint import Duration
from pocs.scheduler.constraint import MoonAvoidance
from panoptes.utils import error
from panoptes.utils import horizon as horizon_utils
from panoptes.utils import load_module
from panoptes.utils.logger import get_root_logger


def create_scheduler_from_config(config, observer=None):
    """ Sets up the scheduler that will be used by the observatory """

    logger = get_root_logger()

    if 'scheduler' not in config:
        logger.info("No scheduler in config")
        return None

    if not observer:
        logger.info("No valid Observer found.")
        return None

    scheduler_config = config.get('scheduler', {})
    scheduler_type = scheduler_config.get('type', 'dispatch')

    # Read the targets from the file
    fields_file = scheduler_config.get('fields_file', 'simple.yaml')
    fields_path = os.path.join(config['directories']['targets'], fields_file)
    logger.debug('Creating scheduler: {}'.format(fields_path))

    if os.path.exists(fields_path):

        try:
            # Load the required module
            module = load_module(
                'pocs.scheduler.{}'.format(scheduler_type))

            obstruction_list = config['location'].get('obstructions', list())
            default_horizon = config['location'].get('horizon', 30 * u.degree)

            horizon_line = horizon_utils.Horizon(
                obstructions=obstruction_list,
                default_horizon=default_horizon.value
            )

            # Simple constraint for now
            constraints = [
                Altitude(horizon=horizon_line),
                MoonAvoidance(),
                Duration(default_horizon)
            ]

            # Create the Scheduler instance
            scheduler = module.Scheduler(
                observer, fields_file=fields_path, constraints=constraints)
            logger.debug("Scheduler created")
        except error.NotFound as e:
            raise error.NotFound(msg=e)
    else:
        raise error.NotFound(
            msg="Fields file does not exist: {}".format(fields_file))

    return scheduler
