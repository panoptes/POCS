import logging
import logging.config
import time

from .config import load_config


def get_logger(cls, profile=None):
    if not profile:
        # profile = "{}.{}".format(cls.__module__, cls.__name__)
        profile = "{}".format(cls.__module__)

    logger = logging.getLogger(profile)
    return logger


def get_root_logger(profile='panoptes', log_config=None):
    """ Creates a root logger for PANOPTES

    Note:
        This creates the root logger for PANOPTES. All modules except `panoptes.core` should
        use the `get_logger` method located in this same module. See `get_logger` for
        details.

    Returns:
        logger(logging.logger): A configured instance of the logger
    """

    # Get log info from config
    log_config = log_config if log_config else load_config().get('logger', {})

    # Alter the log_config to use UTC times
    if log_config.get('use_utc', False):
        for name, formatter in log_config['formatters'].items():
            log_config['formatters'][name].setdefault('()', _UTCFormatter)

    # Configure the logger
    logging.config.dictConfig(log_config)

    # Get the logger and set as attribute to class
    logger = logging.getLogger(profile)

    return logger


class _UTCFormatter(logging.Formatter):

    """ Simple class to convert times to UTC in the logger """
    converter = time.gmtime
