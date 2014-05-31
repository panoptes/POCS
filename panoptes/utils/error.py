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

class NotFound(Error):

    """ Generic not found class """

    def __init__(self, msg):
        pass
        self.msg = msg
        self.exit_program(msg='Cannot find {}'.format(self.msg))

class MountNotFound(NotFound):

    """ Mount cannot be import """
 
    def __init__(self, msg):
        super(MountNotFound, self).__init__(msg)
        self.exit_program(msg='Problem with mount: {}'.format(msg))

class InvalidMountCommand(Error):

    """ Error raised if attempting to send command that doesn't exist """

    def __init__(self, msg):
        super(InvalidMountCommand, self).__init__()
        self.msg = msg

class BadSerialConnection(Error):

    """ Error raised when serial command is bad """

    def __init__(self, msg):
        super(BadSerialConnection, self).__init__()
        self.logger.error('BadSerialConnection1')
        self.msg = msg

class CameraNotFound(NotFound):

    """ Camera cannot be import """

    def __init__(self, msg):
        super(CameraNotFound, self).__init__(msg)
