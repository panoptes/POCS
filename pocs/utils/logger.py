import json
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
        """ Pre-process the log string

        This allows for `format` style specifiers, e.g. `{:02f}` and
        `{:40s}`, which otherwise aren't supported by python's default
        log formatting.
        """
        log_str = fmt
        if len(args) > 0 or len(kwargs) > 0:
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

    def critical(self, fmt, *args, **kwargs):
        self.logger.critical(self._process_str(fmt, *args, **kwargs))


# We don't want to create multiple root loggers that are "identical",
# so track the loggers in a dict keyed by a tuple of:
#    (profile, json_serialized_logger_config).
all_loggers = {}


def get_root_logger(profile='panoptes', log_config=None):
    """ Creates a root logger for PANOPTES used by the PanBase object
    Returns:
        logger(logging.logger): A configured instance of the logger
    """

    # Get log info from config
    log_config = log_config if log_config else load_config('log').get('logger', {})

    # If we already created a logger for this profile and log_config, return that.
    logger_key = (profile, json.dumps(log_config, sort_keys=True))
    logger_for_config = all_loggers.get(logger_key, None)
    if logger_for_config:
        return logger_for_config

    # Alter the log_config to use UTC times
    if log_config.get('use_utc', True):
        for name, formatter in log_config['formatters'].items():
            log_config['formatters'][name].setdefault('()', _UTCFormatter)
        log_fname_datetime = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    else:
        log_fname_datetime = datetime.datetime.now().strftime('%Y%m%dT%H%M%SZ')

    # Setup log file names
    invoked_script = os.path.basename(sys.argv[0])
    log_dir = '{}/logs'.format(os.getenv('PANDIR', gettempdir()))
    log_fname = '{}-{}-{}'.format(invoked_script, os.getpid(), log_fname_datetime)
    log_symlink = '{}/{}.log'.format(log_dir, invoked_script)

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
                os.unlink(log_symlink)
            except FileNotFoundError:
                pass
            finally:
                os.symlink(full_log_fname, log_symlink)

    # Configure the logger
    logging.config.dictConfig(log_config)

    # Get the logger and set as attribute to class
    logger = logging.getLogger(profile)

    # Don't want log messages from state machine library, it is very noisy and
    # we have our own way of logging state transitions
    logging.getLogger('transitions.core').setLevel(logging.WARNING)

    try:
        import coloredlogs
        coloredlogs.install()
    except Exception:  # pragma: no cover
        pass

    logger = PanLogger(logger)
    logger.info('{:*^80}'.format(' Starting PanLogger '))
    all_loggers[logger_key] = logger
    return logger


class _UTCFormatter(logging.Formatter):

    """ Simple class to convert times to UTC in the logger """
    converter = time.gmtime
