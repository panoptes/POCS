import logging
import panoptes.utils.config as config

def has_logger(Class, level=None):
    """ 
    The class decorator. Adds the self.logger to the class. Note that 
    log level can be passed in with decorator so different classes can
    have different levels 
    """
    has_logger.log.info("Adding logging to: {}".format(Class.__name__))
    setattr(Class, 'logger', Logger(log_level=level, profile=Class.__name__))
    return Class


def set_log_level(level='debug'):
    def decorator(Class):
        Class.logger.logger.setLevel(log_levels.get(level))
        return Class
    return decorator


log_levels = {
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warning': logging.WARNING,
    'warn': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG,
}

@config.has_config
class Logger():

    """
        Sets up the logger for our program. The has_logger class decorator allows this to be
        applited to classes within a project
    """

    def __init__(self,log_level=None, profile=None):
        # Get log info from config
        self.log_dir = self.config.setdefault('log_dir', '/var/log/Panoptes/')
        self.log_file = self.config.setdefault('log_file', 'panoptes.log')
        self.log_level = log_level if log_level is not None else self.config.setdefault('log_level', 'info')
        self.log_format = self.config.setdefault('log_format', '%(asctime)23s %(name)20s %(levelname)8s: %(message)s')
        self.log_profile = profile if profile is not None else self.config.setdefault('log_profile', 'PanoptesLogger')

        self.logger = logging.getLogger(self.log_profile)
        # self.file_name = "{}/{}".format(log_dir, log_file)
        self.log_format = logging.Formatter(self.log_format)
        self.logger.setLevel(log_levels[self.log_level])

        # Set up file output
        self.log_fh = logging.FileHandler(self.log_file)
        self.log_fh.setLevel(log_levels[self.log_level])
        self.log_fh.setFormatter(self.log_format)
        self.logger.addHandler(self.log_fh)

        # Set up console output
        # Please leave this in, but commented out if you don't want log output to console
#         self.log_ch = logging.StreamHandler()
#         self.log_ch.setLevel(log_levels[self.log_level])
#         self.log_ch.setFormatter(self.log_format)
#         self.logger.addHandler(self.log_ch)


    def debug(self, msg):
        """ Send a debug message """

        self.logger.debug(msg)

    def info(self, msg):
        """ Send an info message """

        self.logger.info(msg)

    def error(self, msg):
        """ Send an error message """

        self.logger.error(msg)

    def warning(self, msg):
        """ Send an warning message """

        self.logger.warning(msg)

    def critical(self, msg):
        """ Send an critical message """

        self.logger.critical(msg)

    def exception(self, msg):
        """ Send an exception message """

        self.logger.exception(msg)

has_logger.log = Logger()