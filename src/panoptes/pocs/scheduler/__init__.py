"""Scheduler package helpers.

Provides factory functions to construct a Scheduler instance and its list of
constraints from PANOPTES configuration. The module avoids importing concrete
classes directly; instead it dynamically loads the configured scheduler and
constraints using panoptes.utils.library.load_module.
"""
from pathlib import Path
from typing import List

from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.library import load_module

from panoptes.pocs.scheduler.constraint import BaseConstraint
from panoptes.pocs.utils.location import create_location_from_config, download_iers_a_file
from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


def create_scheduler_from_config(config=None, observer=None, iers_url=None, *args, **kwargs):
    """Construct a Scheduler instance based on configuration.

    Reads the 'scheduler' section from the config, ensures IERS tables are
    configured, resolves the observing site (Observer), and loads the configured
    Scheduler class and fields file. Any configured constraints are built via
    create_constraints_from_config and passed to the Scheduler constructor.

    Args:
        config (dict | None): Scheduler configuration; if None, fetched via get_config.
        observer (astroplan.Observer | None): Existing Observer; if None, created from config.
        iers_url (str | None): Optional override for the IERS A table URL.
        *args: Additional positional args forwarded to the Scheduler constructor.
        **kwargs: Additional keyword args forwarded to the Scheduler constructor.

    Returns:
        panoptes.pocs.scheduler.dispatch.Scheduler: The constructed Scheduler instance.

    Raises:
        panoptes.utils.error.NotFound: If the fields file cannot be located or module not found.
    """

    scheduler_config = config or get_config("scheduler", default=None)
    logger.info(f"scheduler_config: {scheduler_config!r}")

    if scheduler_config is None or len(scheduler_config) == 0:
        logger.info("No scheduler in config")
        return None

    download_iers_a_file(iers_url=iers_url)

    if not observer:
        logger.debug("No Observer provided, creating location from config.")
        site_details = create_location_from_config()
        observer = site_details.observer

    # Read the targets from the file
    fields_file = Path(scheduler_config.get("fields_file", "simple.yaml"))
    base_dir = Path(str(get_config("directories.base", default=".")))
    fields_dir = Path(str(get_config("directories.fields", default="./conf_files/fields")))
    fields_path = base_dir / fields_dir / fields_file
    logger.info(f"Creating fields from path: {fields_path}")

    if fields_path.exists():
        scheduler_type = scheduler_config.get("type", "panoptes.pocs.scheduler.dispatch")

        try:
            # Load the required module
            module = load_module(f"{scheduler_type}")

            constraints = create_constraints_from_config(config=scheduler_config)

            # Create the Scheduler instance
            pocs_scheduler = module.Scheduler(
                observer, fields_file=str(fields_path), constraints=constraints, *args, **kwargs
            )
            logger.debug("Scheduler created")
        except error.NotFound as e:
            raise error.NotFound(msg=e)
    else:
        raise error.NotFound(msg=f"Fields file does not exist: {fields_path=!r}")

    return pocs_scheduler


def create_constraints_from_config(config=None) -> List[BaseConstraint]:
    """Build a list of constraint instances from scheduler configuration.

    Reads the 'scheduler.constraints' list from the provided config (or global
    config if None), resolves each constraint's dotted Python path (falling back
    to panoptes.pocs.scheduler.constraint.<Name> when a short name is given), and
    instantiates the constraint with any provided options.

    Args:
        config (dict | None): Scheduler configuration dict; if None, use get_config('scheduler').

    Returns:
        list[BaseConstraint]: Instantiated constraint objects ready to pass to the Scheduler.
    """
    config = config or get_config("scheduler", default=dict())
    constraints = list()
    for constraint_config in config.get("constraints", list()):
        name = constraint_config["name"]

        if len(name.split(".")) < 2:
            name = f"panoptes.pocs.scheduler.constraint.{name}"

        try:
            constraint_module = load_module(name)
        except error.NotFound:
            logger.warning(f"Invalid constraint config given: {constraint_config=}")
        else:
            options = constraint_config.get("options", dict())
            constraints.append(constraint_module(**options))

    return constraints
