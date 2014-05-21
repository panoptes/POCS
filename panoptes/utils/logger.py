import logging
import os

def has_logger(Class, level='debug'):
    """ 
    The class decorator. Adds the self.logger to the class. Note that 
    log level can be passwed in with decorator so different classes can
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
    'info': logging.INFO,
    'debug': logging.DEBUG,
}


class Logger():

    """
        Sets up the logger for our program. The has_logger class decorator allows this to be
        applited to classes within a project
    """

    def __init__(self,
                 log_file=os.path.join('/', 'var', 'log', 'Panoptes', 'panoptes.log'),
                 profile='PanoptesLogger',
                 log_level='debug',
                 log_format='%(asctime)23s %(name)20s %(levelname)8s: %(message)s',
                 ):

        self.logger = logging.getLogger(profile)

        self.file_name = log_file
        self.log_format = logging.Formatter(log_format)

        self.logger.setLevel(log_levels[log_level])

        # Set up file output
        self.log_fh = logging.FileHandler(self.file_name)
        self.log_fh.setLevel(log_levels[log_level])
        self.log_fh.setFormatter(self.log_format)
        self.logger.addHandler(self.log_fh)
        
        # Set up console output
        self.log_ch = logging.StreamHandler()
        self.log_ch.setLevel(logging.DEBUG)
        self.log_ch.setFormatter(self.log_format)
        self.logger.addHandler(self.log_ch)

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