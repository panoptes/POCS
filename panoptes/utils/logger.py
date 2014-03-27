import logging

class Logger():

    """
        Sets up the logger for our program
    """

    def __init__(self, 
        log_file='panoptes.log', 
        profile='PanoptesLogger', 
        log_level=logging.DEBUG,
        log_format='%(asctime)23s %(levelname)8s: %(message)s',
        ):

        self.logger = logging.getLogger(profile)
        self.file_name = log_file

        self.logger.setLevel(log_level)

        self.log_format = logging.Formatter(log_format)

        # Set up file output
        self.log_fh = logging.FileHandler(self.file_name)
        self.log_fh.setLevel(log_level)
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