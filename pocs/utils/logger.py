import datetime
import logging
import logging.config
import os
import time


from .config import load_config


def get_root_logger(profile='panoptes', log_config=None):
    """ Creates a root logger for PANOPTES used by the PanBase object

    Returns:
        logger(logging.logger): A configured instance of the logger
    """

    # Get log info from config
    log_config = log_config if log_config else load_config('log').get('logger', {})

    log_dir = '{}/logs'.format(os.getenv('PANDIR', '/var/panoptes/'))
    log_fname = 'panoptes-{}-{}.log'.format(os.getpid(), datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'))
    log_fname_generic = 'panoptes.log'

    # Alter the log_config to use UTC times
    if log_config.get('use_utc', True):
        for name, formatter in log_config['formatters'].items():
            log_config['formatters'][name].setdefault('()', _UTCFormatter)

    log_file_lookup = {
        'all': "{}/{}".format(log_dir, log_fname),
        'warn': "{}/warnings.log".format(log_dir),
    }

    # Setup the TimeedRotatingFileHandler to backup in middle of day intead of middle of night
    for handler in log_config.get('handlers', []):
        log_config['handlers'][handler].setdefault('filename', log_file_lookup[handler])
        if handler in ['all', 'warn']:
            log_config['handlers'][handler].setdefault('atTime', datetime.time(hour=11, minute=30))

    # Configure the logger
    logging.config.dictConfig(log_config)

    # Get the logger and set as attribute to class
    logger = logging.getLogger(profile)

    # Don't want log messages from state machine library
    logging.getLogger('transitions.core').setLevel(logging.WARNING)

    # Symlink the log file to $PANDIR/logs/panoptes.log
    try:
        os.unlink('{}/{}'.format(log_dir, log_fname_generic))
    except FileNotFoundError:
        pass
    finally:
        os.symlink(log_file_lookup['all'], '{}/{}'.format(log_dir, log_fname_generic))

    try:
        import coloredlogs
        coloredlogs.install()
    except Exception:  # pragma: no cover
        pass

    return logger


class _UTCFormatter(logging.Formatter):

    """ Simple class to convert times to UTC in the logger """
    converter = time.gmtime
