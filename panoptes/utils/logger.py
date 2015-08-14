import sys
import logging

from .config import load_config

def has_logger(Class, level='warning'):
    """Class decorator to add logging

    Args:
        level (str): log level to set for the class wrapper, defaults to 'warning'
    """
    has_logger.log.info("Adding {} logging to: {}".format(level, Class.__name__))
    setattr(Class, 'logger', Logger(log_level=level,profile=Class.__name__))
    return Class


def set_log_level(level='info'):
    """Sets the log level for the class

    Args:
        level (str): log level to set for the class wrapper, defaults to 'warning'
    """
    def decorator(Class):
        has_logger.log.info('Setting log level to {}'.format(level))
        Class.logger.logger.setLevel(log_levels.get(level))
        Class.logger.log_fh.setLevel(log_levels.get(level))
        return Class
    return decorator


log_levels = {
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG,
}

class Logger(logging.Logger):
    """ Consistent logging class for application

        The has_logger class decorator allows this to be
        applited to classes within a project for consistent functionality
    """

    def __init__(self,log_level='warning',profile=None):
        super().__init__(name=profile)

        # Get log info from config
        self.config = load_config()
        log_config = self.config.get('log', {})

        self.log_dir = log_config.setdefault('log_dir', '/var/panoptes/logs')
        self.log_file = log_config.setdefault('log_file', 'panoptes.log')
        self.log_level = log_config.setdefault('log_level', 'info')
        self.log_format = log_config.setdefault('log_format', '%(asctime)23s %(name)15s %(levelname)8s: %(message)s')
        self.log_profile = profile if profile is not None else log_config.setdefault('log_profile', 'PanoptesLogger')

        self.logger = logging.getLogger(self.log_profile)
        self.log_format = logging.Formatter(self.log_format)
        self.logger.setLevel(log_levels[self.log_level])

        fh = "{}/{}".format(self.log_dir, self.log_file)

        # Set up file output
        self.log_fh = logging.FileHandler(fh)
        self.log_fh.setLevel(log_levels[self.log_level])
        self.log_fh.setFormatter(self.log_format)
        self.logger.addHandler(self.log_fh)

    def debug(self, msg):
        """ Send a debug message """

        self.logger.debug(msg)

    def info(self, msg):
        """ Send an info message """

        self.logger.info(msg)

    def error(self, msg):
        """ Send an error message """

        self.logger.warning(self.logger.findCaller())
        self.logger.error(msg)

    def warning(self, msg):
        """ Send an warning message """

        self.logger.warning(self.logger.findCaller())
        self.logger.warning(msg)

    def critical(self, msg):
        """ Send an critical message """

        self.logger.warning(self.logger.findCaller())
        self.logger.critical(msg)

    def exception(self, msg):
        """ Send an exception message """

        self.logger.warning(self.logger.findCaller())
        self.logger.exception(msg)

has_logger.log = Logger()
