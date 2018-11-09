import collections
import datetime
import json
import logging
import logging.config
import os
import re
import string
import sys
from tempfile import gettempdir
import time
from warnings import warn

from pocs.utils.config import load_config

# We don't want to create multiple root loggers that are "identical",
# so track the loggers in a dict keyed by a tuple of:
#    (profile, json_serialized_logger_config).
all_loggers = {}


def field_name_to_key(field_name):
    """Given a field_name from Formatter.parse(), extract the argument key.

    Args:
        field_name: expression used to identify the source of the value for
            a field. See string.Formatter.parse for more info.

    Returns:
        The name or index at the start of the field_name.
    """
    assert isinstance(field_name, str)
    assert len(field_name)
    m = re.match(r'^([^.[]+)', field_name)
    if not m:
        return None
    arg_name = m.group(1)
    if arg_name.isdigit():
        return int(arg_name)
    else:
        return arg_name


def format_has_reference_keys(fmt, args):
    """Does fmt have named references in it?

    Args:
        fmt: A format string of the type supported by string.Formatter.
        args: A dictionary which *may* be providing values to be formatted
            according to the format fmt.

    Returns:
        True if fmt has any format substitution field that references an
        entry in args by a string key. False otherwise.
    """
    assert isinstance(args, dict)
    try:
        for literal_text, field_name, format_spec, conversion in string.Formatter().parse(fmt):
            if field_name:
                key = field_name_to_key(field_name)
                if isinstance(key, str) and key in args:
                    return True
    except Exception:
        pass
    return False


def format_has_legacy_style(fmt):
    """Does fmt have a % in it? I.e. is it a legacy style?

    We replace two %%'s in a row with nothing, see if any percents are
    left.
    """
    fmt = fmt.replace('%%', '')
    return '%' in fmt


# formatting_methods encapsulates the different ways that we can apply
# a format string to a dictionary of args. Those starting with legacy_
# use the original printf style operator '%'. Those starting with
# modern_ use the Advanced String Formatting method defined in PEP 3101.
formatting_methods = dict(
    legacy_direct=lambda fmt, args: fmt % args,
    legacy_tuple=lambda fmt, args: fmt % (args, ),
    modern_direct=lambda fmt, args: fmt.format(args),
    modern_args=lambda fmt, args: fmt.format(*args),
    modern_kwargs=lambda fmt, args: fmt.format(**args),
)


def logger_msg_formatter(fmt, args):
    """Returns the formatted logger message.

    Python's logger package uses the old printf style formatting
    strings, rather than the newer PEP-3101 "Advanced String Formatting"
    style of formatting strings.

    This function supports using either style, though not both in one
    string. It examines msg to look for which style is in use,
    and is exposed as a function for easier testing.

    The logging package assumes that if the sole argument to the logger
    call is a dict, that the caller intends to use that dict as a source
    for mapping key substitutions in the formatting operation, so
    discards the sequence that surrounded the dict (as part of *args),
    keeping only the dict as the value of logging.LogRecord.args here.
    It happens that the old style formatting operator '%' would detect
    whether the string included keys mapping into the dict on the right
    hand side of the % operator, and if so would look them up; however,
    if the formatting string didn't include mapping keys, then a sole
    dict arg was treated as a single value, thus permitting a single
    substitution (e.g. 'This is the result: %r' % some_dict).

    The .format() method of strings doesn't have the described behavior,
    so this formatter class attempts to provide it.
    """
    if not args:
        return fmt

    # There are args, so fmt must be a format string. Select the
    # formatting methods to try based on the contents.
    method_names = []
    may_have_legacy_subst = format_has_legacy_style(fmt)
    args_are_mapping = isinstance(args, collections.Mapping)
    if '{' in fmt:
        # Looks modern.
        if args_are_mapping:
            if format_has_reference_keys(fmt, args):
                method_names.append('modern_kwargs')
            else:
                method_names.append('modern_direct')
        else:
            method_names.append('modern_args')
    if may_have_legacy_subst:
        # Looks old school.
        method_names.append('legacy_direct')

    # Add fallback methods.
    def add_fallback(name):
        if name not in method_names:
            method_names.append(name)
    if '{' in fmt:
        add_fallback('modern_direct')
    if may_have_legacy_subst:
        add_fallback('legacy_tuple')
    elif '%' in fmt:
        add_fallback('legacy_direct')

    # Now try to format:
    for method_name in method_names:
        try:
            method = formatting_methods[method_name]
            return method(fmt, args)
        except Exception:
            pass

    warn(f'Unable to format log.')
    warn(f'Log message (format string): {fmt!r}')
    warn('Log args type: %s' % type(args))
    try:
        warn(f'Log args: {args!r}')
    except Exception:  # pragma: no cover
        warn('Unable to represent log args in string form.')
    return fmt


class StrFormatLogRecord(logging.LogRecord):
    """Allow for `str.format` style log messages

    Even though you can select '{' as the style for the formatter class,
    you still can't use {} formatting for your message. The custom
    `getMessage` tries new format, then falls back to legacy format.

    Originally inspired by https://goo.gl/Cyt5NH but much changed since
    then.
    """

    def getMessage(self):
        msg = str(self.msg)
        return logger_msg_formatter(msg, self.args)


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
        if 'formatters' not in log_config:  # pragma: no cover
            # TODO(jamessynge): Raise a custom exception in this case instead
            # of issuing a warning; after all, a standard dict will throw a
            # KeyError in the for loop below if 'formatters' is missing.
            warn('formatters is missing from log_config!')
            warn(f'log_config: {log_config!r}')
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

    logger.info('{:*^80}'.format(' Starting PanLogger '))
    # TODO(jamessynge) Output name of script, cmdline args, etc. And do son
    # when the log rotates too!
    all_loggers[logger_key] = logger
    return logger


class _UTCFormatter(logging.Formatter):
    """ Simple class to convert times to UTC in the logger """
    converter = time.gmtime
