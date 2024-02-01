from pathlib import Path
from typing import List, Optional

from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.library import load_module

from panoptes.pocs.scheduler.constraint import Altitude, BaseConstraint
from panoptes.pocs.scheduler.constraint import Duration
from panoptes.pocs.scheduler.constraint import MoonAvoidance
from panoptes.pocs.scheduler.scheduler import BaseScheduler  # noqa; needed for import
from panoptes.pocs.utils.location import create_location_from_config
from panoptes.pocs.utils.logger import get_logger
from panoptes.pocs.utils.location import download_iers_a_file

logger = get_logger()


def create_scheduler_from_config(config=None, observer=None, iers_url=None, *args,
                                 **kwargs) -> Optional[BaseScheduler]:
    """ Sets up the scheduler that will be used by the observatory """

    scheduler_config = config or get_config('scheduler', default=None)
    logger.info(f'scheduler_config: {scheduler_config!r}')

    if scheduler_config is None or len(scheduler_config) == 0:
        logger.info("No scheduler in config")
        return None

    download_iers_a_file(iers_url=iers_url)

    if not observer:
        logger.debug(f'No Observer provided, creating location from config.')
        site_details = create_location_from_config()
        observer = site_details.observer

    # Read the targets from the file
    fields_file = Path(scheduler_config.get('fields_file', 'simple.yaml'))
    base_dir = Path(str(get_config('directories.base', default='.')))
    fields_dir = base_dir / Path(str(get_config('directories.fields', default='./conf_files/fields')))
    fields_path = fields_dir / fields_file
    logger.debug(f'Creating scheduler: {fields_path}')

    if fields_path.exists():
        scheduler_type = scheduler_config.get('type', 'panoptes.pocs.scheduler.dispatch')

        try:
            # Load the required module
            module = load_module(f'{scheduler_type}')

            constraints = create_constraints_from_config(config=scheduler_config)

            # Create the Scheduler instance
            pocs_scheduler = module.Scheduler(observer,
                                              fields_file=str(fields_path),
                                              constraints=constraints,
                                              *args, **kwargs)
            logger.debug("Scheduler created")
        except error.NotFound as e:
            raise error.NotFound(msg=e)
    else:
        raise error.NotFound(msg=f"Fields file does not exist: {fields_path=!r}")

    return pocs_scheduler


def create_constraints_from_config(config=None) -> List[BaseConstraint]:
    scheduler_config = config or get_config('scheduler', default=dict())
    constraints = list()
    for constraint_config in scheduler_config.get('constraints', list()):
        name = constraint_config['name']
        try:
            constraint_module = load_module(name)
        except error.NotFound:
            logger.warning(f'Invalid constraint config given: {constraint_config=}')
        else:
            options = constraint_config.get('options', dict())
            constraints.append(constraint_module(**options))

    return constraints
