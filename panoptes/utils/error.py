import sys

import panoptes.utils.logger as logger


@logger.has_logger
class Error(Exception):

    """ Base class for Panoptes errors """

    def exit_program(self, msg='No reason specified'):
        """ Kills running program """
        self.logger.error("TERMINATING: {}".format(msg))
        sys.exit()


class InvalidConfig(Error):

    """ Error raised if config file is invalid """

    def __init__(self, msg):
        super(InvalidConfig, self).__init__()
        self.msg = msg

    def __str__(self):
        return self.msg


class NotFound(Error):

    """ Generic not found class """

    def __init__(self, msg):
        self.msg = msg
        self.exit_program(msg='Cannot find {}'.format(self.msg))

    def __str__(self):
        return self.msg


class MountNotFound(Error):

    """ Mount cannot be import """

    def __init__(self, msg):
        super(MountNotFound, self).__init__(msg)


class CameraNotFound(NotFound):

    """ Camera cannot be import """

    def __init__(self, msg):
        super(CameraNotFound, self).__init__(msg)
