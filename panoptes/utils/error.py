import sys

from astropy.utils.exceptions import AstropyWarning

from .logger import has_logger

@has_logger
class PanError(AstropyWarning):

    """ Base class for Panoptes errors """
    def __init__(self, msg=None, exit=False):
        if msg:
            self.logger.error('{}: {}'.format(self.__class__.__name__,msg))
            self.msg = msg

        if exit:
            self.exit_program()

    def exit_program(self, msg='No reason specified'):
        """ Kills running program """
        self.logger.error("TERMINATING: {}".format(msg))
        sys.exit(1)

class InvalidSystemCommand(PanError):
    """ Error for a system level command malfunction """
    def __init__(self,msg='Problem running system command'):
        super().__init__(msg=msg)

class NotFound(PanError):
    """ Generic not found class """
    pass

class InvalidConfig(PanError):
    """ PanError raised if config file is invalid """
    pass

class InvalidMountCommand(PanError):
    """ PanError raised if attempting to send command that doesn't exist """
    pass

class BadSerialConnection(PanError):
    """ PanError raised when serial command is bad """
    pass

class MountNotFound(NotFound):
    """ Mount cannot be import """

    def __init__(self,msg='Mount Not Found'):
        self.exit_program(msg=msg)

class MongoCollectionNotFound(NotFound):
    """ MongoDB collection cannot be found """

    def __init__(self,msg='Collection not found'):
        self.exit_program(msg=msg)

class CameraNotFound(NotFound):
    """ Camera cannot be import """
    pass
