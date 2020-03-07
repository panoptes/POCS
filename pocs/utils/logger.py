import os
from contextlib import suppress
from loguru import logger


class PanLogger:

    """Custom formatter to have dynamic widths for logging.

    See https://loguru.readthedocs.io/en/stable/resources/recipes.html#dynamically-formatting-messages-to-properly-align-values-with-padding

    """

    def __init__(self):
        self.padding = 0
        self.fmt = "<lvl>{level:.1s}</lvl> <light-blue>{time:MM-DD HH:mm:ss.ss!UTC}</> <blue>({time:HH:mm:ss.ss})</> | <c>{name} {function}:{line}{extra[padding]}</c> | <lvl>{message}</lvl>\n"
        self.handlers = set()

    def format(self, record):
        length = len("{name}:{function}:{line}".format(**record))
        self.padding = max(self.padding, length)
        record["extra"]["padding"] = " " * (self.padding - length)
        return self.fmt


LOGGER_INFO = PanLogger()


def get_logger(profile='panoptes',
               console_log_file='panoptes.log',
               full_log_file='panoptes_{time:YYYYMMDD!UTC}.log',
               log_dir=None,
               log_level='DEBUG',
               stderr=False):
    """Creates a root logger for PANOPTES used by the PanBase object.

    Two log files are created, one suitable for viewing on the console (via `tail`)
    and a full log file suitable for archive and later inspection. The full log
    file is serialized into JSON.

    Note: The `log_dir` is determined first from `$PANLOG` if it exists, then
      `$PANDIR/logs` if `$PANDIR` exists, otherwise defaults to `.`.

    Args:
        profile (str, optional): The name of the logger to use, defaults to 'panoptes'.
        console_log_file (str|None, optional): Filename for the file that is suitable for
            tailing in a shell (i.e., read by humans). This file is rotated daily however
            the files are not retained.
        full_log_file (str|None, optional): Filename for log file that includes all levels
            and is serialized and rotated automatically. Useful for uploading to log service
            website. Defaults to `panoptes_{time:YYYYMMDD!UTC}.log.gz` with a daily rotation
            at 11:30am and a 7 day retention policy. If `None` then no file will be generated.
        log_dir (str|None, optional): The directory to place the log file, see note.
        log_level (str, optional): Log level for console output, defaults to 'DEBUG'.
            Note that it should be a string that matches standard `logging` levels and
            also includes `TRACE` (below `DEBUG`) and `SUCCESS` (above `INFO`).
        stderr (bool, optional): If logs should also be output on `stderr` instead of
            to a file. This is similar to default python logging. For POCS it is preferable
            to write to a file and then tail the file but this is needed for testing and
            might be useful (or annoying) in a console.

    Returns:
        `loguru.logger`: A configured instance of the logger.
    """

    # Create the directory for the per-run files.
    if log_dir is None:
        try:
            log_dir = os.environ['PANLOG']
        except KeyError:
            log_dir = os.path.join(os.getenv('PANDIR', '.'), 'logs')
    log_dir = os.path.normpath(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    # Record the handlers
    logger._handlers = dict()

    if stderr is False:
        with suppress(ValueError):
            logger.remove(0)

        if 'console' not in LOGGER_INFO.handlers:
            console_log_path = os.path.normpath(os.path.join(log_dir, console_log_file))
            logger.add(
                sink=console_log_path,
                rotation='11:30',
                retention=1,
                format=LOGGER_INFO.format,
                enqueue=True,  # multiprocessing
                colorize=True,
                backtrace=True,
                diagnose=True,
                level=log_level)
            LOGGER_INFO.handlers.add('console')

    if 'archive' not in LOGGER_INFO.handlers and full_log_file is not None:
        full_log_path = os.path.normpath(os.path.join(log_dir, full_log_file))
        logger.add(
            sink=full_log_path,
            rotation='11:31',
            retention='7 days',
            compression='gz',
            enqueue=True,  # multiprocessing
            serialize=True,
            backtrace=True,
            diagnose=True,
            level='TRACE')
        LOGGER_INFO.handlers.add('archive')

    return logger
