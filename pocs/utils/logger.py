import json
import os
import sys
import time
import datetime
import logging
import logging.config
from tempfile import gettempdir

from pocs.utils.config import load_config

# We don't want to create multiple root loggers that are "identical",
# so track the loggers in a dict keyed by a tuple of:
#    (profile, json_serialized_logger_config).
all_loggers = {}


class StrFormatLogRecord(logging.LogRecord):
    """ Allow for `str.format` style log messages

    Even though you can select '{' as the style for the formatter class,
    you still can't use {} formatting for your message. The custom
    `getMessage` tries legacy format and then tries new format.

    From: https://goo.gl/Cyt5NH
    """

    def getMessage(self):
        msg = str(self.msg)
        if self.args:
            if '{' in msg:
                try:
                    msg = msg.format(*self.args)
                except (TypeError, ValueError):
                    msg = msg % self.args
            else:
                try:
                    msg = msg % self.args
                except (TypeError, ValueError):
                    msg = msg.format(*self.args)
        return msg


def get_root_logger(profile='panoptes', log_config=None):
    """Creates a root logger for PANOPTES used by the PanBase object.

    Args:
        profile (str, optional): The name of the logger to use, defaults
            to 'panoptes'.
        log_config (dict|None, optional): Configuration options for the logger.
            See https://docs.python.org/3/library/logging.config.html for
            available options. Default is `None`, which then looks up the
            values in the `log.yaml` config file.

    Returns:
        logger(logging.logger): A configured instance of the logger
    """

    # Get log info from config
    log_config = log_config if log_config else load_config('log').get('logger', {})

    # If we already created a logger for this profile and log_config, return that.
    logger_key = (profile, json.dumps(log_config, sort_keys=True))
    try:
        return all_loggers[logger_key]
    except KeyError:
        pass

    # Alter the log_config to use UTC times
    if log_config.get('use_utc', True):
        # TODO(jamessynge): Figure out why 'formatters' is sometimes
        # missing from the log_config. It is hard to understand how
        # this could occur given that none of the callers of
        # get_root_logger pass in their own log_config.
        if 'formatters' not in log_config and sys.stdout.isatty():
            import pdb
            pdb.set_trace()
        for name, formatter in log_config['formatters'].items():
            log_config['formatters'][name].setdefault('()', _UTCFormatter)
        log_fname_datetime = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    else:
        log_fname_datetime = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')

    # Setup log file names
    invoked_script = os.path.basename(sys.argv[0])
    log_dir = os.getenv('PANLOG', '')
    if not log_dir:
        log_dir = os.path.join(os.getenv('PANDIR', gettempdir()), 'logs')
    per_run_dir = os.path.join(log_dir, 'per-run', invoked_script)
    log_fname = '{}-{}-{}'.format(invoked_script, log_fname_datetime, os.getpid())

    # Create the directory for the per-run files.
    os.makedirs(per_run_dir, exist_ok=True)

    # Set log filename and rotation
    for handler in log_config.get('handlers', []):
        # Set the filename
        partial_fname = '{}-{}.log'.format(log_fname, handler)
        full_log_fname = os.path.join(per_run_dir, partial_fname)
        log_config['handlers'][handler].setdefault('filename', full_log_fname)

        # Setup the TimedRotatingFileHandler for middle of day
        log_config['handlers'][handler].setdefault('atTime', datetime.time(hour=11, minute=30))

        # Create a symlink to the log file with just the name of the script and the handler
        # (level), as this makes it easier to find the latest file.
        # Use a relative path, so that if we move PANLOG the paths aren't broken.
        log_symlink = os.path.join(log_dir, '{}-{}.log'.format(invoked_script, handler))
        log_symlink_target = os.path.relpath(full_log_fname, start=log_dir)
        try:
            os.unlink(log_symlink)
        except FileNotFoundError:  # pragma: no cover
            pass
        finally:
            os.symlink(log_symlink_target, log_symlink)

    # Configure the logger
    logging.config.dictConfig(log_config)

    # Get the logger and set as attribute to class
    logger = logging.getLogger(profile)

    # Don't want log messages from state machine library, it is very noisy and
    # we have our own way of logging state transitions
    logging.getLogger('transitions.core').setLevel(logging.WARNING)

    # Set custom LogRecord
    logging.setLogRecordFactory(StrFormatLogRecord)

    # Add a filter for better filename/lineno
    logger.addFilter(FilenameLineFilter())

    logger.info('{:*^80}'.format(' Starting PanLogger '))
    # TODO(jamessynge) Output name of script, cmdline args, etc. And do son
    # when the log rotates too!
    all_loggers[logger_key] = logger
    return logger


class _UTCFormatter(logging.Formatter):

    """ Simple class to convert times to UTC in the logger """
    converter = time.gmtime


class FilenameLineFilter(logging.Filter):
    """Adds a simple concatenation of filename and lineno for fixed length """

    def filter(self, record):

        record.fileline = '{}:{}'.format(record.filename, record.lineno)
        return True
