import os
import sys
import time
import datetime
import logging
import logging.config
from tempfile import gettempdir

from .config import load_config


class PanLogger(object):
    """ Logger for PANOPTES with format style strings """

    def __init__(self, logger):
        super(PanLogger, self).__init__()
        self.logger = logger

    def _process_str(self, fmt, *args, **kwargs):
        log_str = fmt
        if len(args) > 0:
            log_str = fmt.format(*args, **kwargs)

        return log_str

    def debug(self, fmt, *args, **kwargs):
        self.logger.debug(self._process_str(fmt, *args, **kwargs))

    def info(self, fmt, *args, **kwargs):
        self.logger.info(self._process_str(fmt, *args, **kwargs))

    def warning(self, fmt, *args, **kwargs):
        self.logger.warning(self._process_str(fmt, *args, **kwargs))

    def error(self, fmt, *args, **kwargs):
        self.logger.error(self._process_str(fmt, *args, **kwargs))


def get_root_logger(profile='panoptes', log_config=None):
    """ Creates a root logger for PANOPTES used by the PanBase object

    Returns:
        logger(logging.logger): A configured instance of the logger
    """

    # Get log info from config
    log_config = log_config if log_config else load_config('log').get('logger', {})

    invoked_script = os.path.basename(sys.argv[0])
    log_dir = '{}/logs'.format(os.getenv('PANDIR', gettempdir()))
    log_fname = '{}-{}-{}'.format(invoked_script, os.getpid(),
                                  datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'))
    log_fname_generic = invoked_script

    # Alter the log_config to use UTC times
    if log_config.get('use_utc', True):
        for name, formatter in log_config['formatters'].items():
            log_config['formatters'][name].setdefault('()', _UTCFormatter)

    # Set log filename and rotation
    for handler in log_config.get('handlers', []):
        # Set the filename
        full_log_fname = '{}/{}-{}.log'.format(log_dir, log_fname, handler)
        log_config['handlers'][handler].setdefault('filename', full_log_fname)

        # Setup the TimeedRotatingFileHandler for middle of day
        log_config['handlers'][handler].setdefault('atTime', datetime.time(hour=11, minute=30))

        if handler == 'all':
            # Symlink the log file to $PANDIR/logs/panoptes.log
            try:
                os.unlink('{}/{}'.format(log_dir, log_fname_generic))
            except FileNotFoundError:
                pass
            finally:
                os.symlink(full_log_fname, '{}/{}'.format(log_dir, log_fname_generic))

    # Configure the logger
    logging.config.dictConfig(log_config)

    # Get the logger and set as attribute to class
    logger = logging.getLogger(profile)

    # Don't want log messages from state machine library
    logging.getLogger('transitions.core').setLevel(logging.WARNING)

    try:
        import coloredlogs
        coloredlogs.install()
    except Exception:  # pragma: no cover
        pass

    return PanLogger(logger)


class _UTCFormatter(logging.Formatter):

    """ Simple class to convert times to UTC in the logger """
    converter = time.gmtime
