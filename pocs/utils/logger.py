import datetime
import logging
import logging.config
import os
import time


from . import current_time
from .config import load_config


def get_root_logger(profile='panoptes', log_config=None, log_name='panoptes', rotate=True):
    """ Creates a root logger for PANOPTES used by the PanBase object

    Returns:
        logger(logging.logger): A configured instance of the logger
    """

    # Get log info from config
    log_config = log_config if log_config else load_config('log').get('logger', {})

    # Alter the log_config to use UTC times
    if log_config.get('use_utc', True):
        for name, formatter in log_config['formatters'].items():
            log_config['formatters'][name].setdefault('()', _UTCFormatter)

    warning_log_name = 'warnings'

    if rotate:
        log_name += '_' + current_time(flatten=True)
        warning_log_name += '_' + current_time(flatten=True)

    log_file_lookup = {
        'all': "{}/logs/{}.log".format(os.getenv('PANDIR', '/var/panoptes'), log_name),
        'warn': "{}/logs/{}.log".format(os.getenv('PANDIR', '/var/panoptes'), warning_log_name),
    }

    # Symlink logname for easy access
    log_link = "{}/logs/latest.log".format(os.getenv('PANDIR', '/var/panoptes'))
    if os.path.exists(log_link):
        os.remove(log_link)

    os.symlink(log_file_lookup['all'], log_link)

    # Setup the TimeedRotatingFileHandler to backup in middle of day intead of middle of night
    for handler in log_config.get('handlers', []):
        log_config['handlers'][handler].setdefault('filename', log_file_lookup[handler])
        if handler in ['all', 'warn']:
            log_config['handlers'][handler].setdefault('atTime', datetime.time(hour=11, minute=30))

    # Configure the logger
    logging.config.dictConfig(log_config)

    # Get the logger and set as attribute to class
    logger = logging.getLogger(profile)

    logging.getLogger('transitions.core').setLevel(logging.WARNING)

    try:
        import coloredlogs
        coloredlogs.install()
    except Exception:  # pragma: no cover
        pass

    return logger


class _UTCFormatter(logging.Formatter):

    """ Simple class to convert times to UTC in the logger """
    converter = time.gmtime
