import os
from loguru import logger


class ConsoleFormatter:

    """Custom formatter to have dynamic widths for logging.

    See https://loguru.readthedocs.io/en/stable/resources/recipes.html#dynamically-formatting-messages-to-properly-align-values-with-padding

    """

    def __init__(self):
        self.padding = 0
        self.fmt = "<lvl>{level:.1s}</lvl> <blue>{time:MM-DD HH:mm:ss.ss!UTC} ({time:HH:mm:ss.ss})</blue> | {name} {function}:{line}{extra[padding]} | <lvl>{message}</lvl>\n"

    def format(self, record):
        length = len("{name}:{function}:{line}".format(**record))
        self.padding = max(self.padding, length)
        record["extra"]["padding"] = " " * (self.padding - length)
        return self.fmt


FORMATTER = ConsoleFormatter()


def get_logger(profile='panoptes',
               console_log_file='panoptes.log',
               full_log_file='panoptes_{time:YYYYMMDD!UTC}.log',
               log_dir=None,
               log_level='DEBUG'):
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
        full_log_file (str, optional): Filename for log file that includes all levels
            and is serialized and rotated automatically. Useful for uploading to log service
            website. Defaults to `panoptes_{time:YYYYMMDD!UTC}.log.gz` with a daily rotation
            at 11:30am and a 7 day retention policy.
        log_dir (str|None, optional): The directory to place the log file, see note.
        log_level (str, optional): Log level for console output, defaults to 'DEBUG'.
            Note that it should be a string that matches standard `logging` levels and
            also includes `TRACE` (below `DEBUG`) and `SUCCESS` (above `INFO`).

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

    console_log_path = os.path.normpath(os.path.join(log_dir, console_log_file))
    full_log_path = os.path.normpath(os.path.join(log_dir, full_log_file))

    console_handler = dict(
        sink=console_log_path,
        rotation='11:30',
        retention=1,
        format=FORMATTER.format,
        enqueue=True,  # multiprocessing
        colorize=True,
        backtrace=True,
        diagnose=True,
        level=log_level)

    file_handler = dict(
        sink=full_log_path,
        rotation='11:30',
        retention='3 days',
        compression='gz',
        enqueue=True,  # multiprocessing
        serialize=True,
        backtrace=True,
        diagnose=True,
        level='TRACE')

    logger.configure(
        handlers=[
            console_handler,
            file_handler
        ],
    )

    return logger
