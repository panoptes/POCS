import os
from loguru import logger as loguru_logger


class PanLogger:
    """Custom formatter to have dynamic widths for logging.

    Also provides a `handlers` dictionary to track attached handlers by id.

    See https://loguru.readthedocs.io/en/stable/resources/recipes.html#dynamically-formatting-messages-to-properly-align-values-with-padding

    """

    def __init__(self):
        self.padding = 0
        # Level Time_UTC Time_Local dynamic_padding Message
        self.fmt = "<lvl>{level:.1s}</lvl> " \
                   "<light-blue>{time:MM-DD HH:mm:ss.ss!UTC}</>" \
                   "<blue>({time:HH:mm:ss.ss})</> " \
                   "| <c>{name} {function}:{line}{extra[padding]}</c> | " \
                   "<lvl>{message}</lvl>\n"
        self.handlers = dict()

    def format(self, record):
        length = len("{name}:{function}:{line}".format(**record))
        self.padding = max(self.padding, length)
        record["extra"]["padding"] = " " * (self.padding - length)
        return self.fmt


# Create a global singleton to hold the handlers and padding info.
LOGGER_INFO = PanLogger()


def get_logger(profile='panoptes',
               console_log_file='panoptes.log',
               full_log_file='panoptes_{time:YYYYMMDD!UTC}.log',
               log_dir=None,
               log_level='DEBUG'):
    """Creates a root logger for PANOPTES used by the PanBase object.

    Two log files are created, one suitable for viewing on the console (via `tail`)
    and a full log file suitable for archive and later inspection. The full log
    file is serialized into JSON.

    Note: This clobbers all existing loggers and forces the two files.

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

    Returns:
        `loguru.logger`: A configured instance of the logger.
    """

    if log_dir is None:
        try:
            log_dir = os.environ['PANLOG']
        except KeyError:
            log_dir = os.path.join(os.getenv('PANDIR', '.'), 'logs')
    log_dir = os.path.normpath(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    # Log file for tailing on the console.
    if 'console' not in LOGGER_INFO.handlers:
        console_log_path = os.path.normpath(os.path.join(log_dir, console_log_file))
        console_id = loguru_logger.add(
            console_log_path,
            rotation='11:30',
            retention=1,
            format=LOGGER_INFO.format,
            enqueue=True,  # multiprocessing
            colorize=True,
            backtrace=True,
            diagnose=True,
            compression='gz',
            level=log_level)
        LOGGER_INFO.handlers['console'] = console_id

    # Log file for ingesting into log file service.
    if full_log_file and 'archive' not in LOGGER_INFO.handlers:
        full_log_path = os.path.normpath(os.path.join(log_dir, full_log_file))
        archive_id = loguru_logger.add(
            full_log_path,
            rotation='11:31',
            retention='7 days',
            compression='gz',
            enqueue=True,  # multiprocessing
            serialize=True,
            backtrace=True,
            diagnose=True,
            level='TRACE')
        LOGGER_INFO.handlers['archive'] = archive_id

    # Customize colors
    loguru_logger.level('TRACE', color='<cyan>')
    loguru_logger.level('DEBUG', color='<white>')
    loguru_logger.level('INFO', color='<light-blue><bold>')
    loguru_logger.level('SUCCESS', color='<cyan><bold>')

    return loguru_logger
