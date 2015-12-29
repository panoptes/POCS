import logging
import logging.config
import time

from .config import load_config

log_levels = {
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG,
}


def has_logger(Class, level='info'):
    """Class decorator to add logging

    This assumes a root logger has been created by `create_logger`. This class-level
    method will return an instance of the logger with the appropriate child-level
    namespace

    Args:
        level (str): log level to set for the class wrapper, defaults to 'warning'
    """
    profile = "{}.{}".format(Class.__module__, Class.__name__)
    setattr(Class, 'logger', logging.getLogger(profile))
    return Class


def root_logger(Class, log_config=None):
    """ Creates a root logger for PANOPTES

    Note:
        This creates the root logger for PANOPTES. All modules except `panoptes.core` should
        use the `has_logger` class method located in this same module. See `has_logger` for
        details.

    Returns:
        logger(logging.logger): A configured instance of the logger
    """

    # Get log info from config
    log_config = log_config if log_config else load_config().get('logger', {})

    # Alter the log_config to use UTC times
    log_config['formatters']['detail'].setdefault('()', UTCFormatter)
    log_config['formatters']['simple'].setdefault('()', UTCFormatter)

    # Configure the logger
    logging.config.dictConfig(log_config)

    # Get the logger and set as attribute to class
    logger = logging.getLogger('panoptes')
    setattr(Class, 'logger', logger)

    return Class


class UTCFormatter(logging.Formatter):
    converter = time.gmtime
