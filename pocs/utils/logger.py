import os
import sys
from loguru import logger


def get_logger(profile='panoptes',
               log_file='panoptes_{time:YYYYMMDD!UTC}.log',
               log_dir=None,
               log_level='DEBUG',
               serialize=True,
               stderr=False):
    """Creates a root logger for PANOPTES used by the PanBase object.

    Note: The `log_dir` is determined first from `$PANLOG` if it exists, then
      `$PANDIR/logs` if `$PANDIR` exists, otherwise defaults to `.`.

    Args:
        profile (str, optional): The name of the logger to use, defaults to 'panoptes'.
        log_file (str|None, optional): The filename, defaults to `panoptes_{time:YYYYMMDD!UTC}.log`.
        log_dir (str|None, optional): The directory to place the log file, see note.
        log_level (str, optional): Log level, defaults to 'DEBUG'. Note that it should be
            a string that matches standard `logging` levels and also includes `TRACE`
            (below `DEBUG`) and `SUCCESS` (above `INFO`)
        serialize (bool, optional): If logs should be serialized to JSON, default True.
        stderr (bool, optional): If the default `stderr` handler should be included,
          defaults to False.


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

    console_fmt = '{time}  {message}'

    log_path = os.path.normpath(os.path.join(log_dir, log_file))

    console_handler = dict(
        sink=sys.stderr,
        format=console_fmt,
        colorize=True,
        backtrace=True,
        diagnose=True,
        level=log_level)

    file_handler = dict(
        sink=log_path,
        rotation='11:30',
        enqueue=True,  # multiprocessing
        serialize=serialize,
        backtrace=True,
        diagnose=True,
        level=log_level)

    logger.configure(
        handlers=[
            console_handler,
            file_handler
        ],
        activation=[
            ("", stderr),
            (profile, True)
        ]
    )

    return logger
