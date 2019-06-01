import sys

from pocs.utils.logger import get_root_logger

logger = get_root_logger()


class PanError(Exception):

    """ Base class for Panoptes errors """

    def __init__(self, msg=None, exit=False):
        self.msg = msg

        if self.msg:
            logger.error(str(self))

        if exit:
            self.exit_program(self.msg)

    def exit_program(self, msg=None):
        """ Kills running program """
        if not msg:
            self.msg = 'No reason specified'

        print("TERMINATING: {}".format(self.msg))
        sys.exit(1)

    def __str__(self):
        error_str = str(self.__class__.__name__)
        if self.msg:
            error_str += ': {}'.format(self.msg)

        return error_str


class InvalidSystemCommand(PanError):

    """ Error for a system level command malfunction """

    def __init__(self, msg='Problem running system command'):
        super().__init__(msg)


class Timeout(PanError):

    """ Error called when an event times out """

    def __init__(self, msg='Timeout waiting for event'):
        super().__init__(msg)


class NoObservation(PanError):

    """ Generic no Observation """

    def __init__(self, msg='No valid observations found.'):
        super().__init__(msg)


class NotFound(PanError):

    """ Generic not found class """
    pass


class InvalidCollection(NotFound):
    """PanError raised if a collection name is invalid."""
    pass


class InvalidConfig(PanError):

    """ PanError raised if config file is invalid """
    pass


class InvalidCommand(PanError):

    """ PanError raised if a system command does not run """
    pass


class InvalidMountCommand(PanError):

    """ PanError raised if attempting to send command that doesn't exist """
    pass


class InvalidObservation(NotFound):
    """PanError raised if a field is invalid."""
    pass


class BadConnection(PanError):

    """ PanError raised when a connection is bad """
    pass


class BadSerialConnection(PanError):

    """ PanError raised when serial command is bad """
    pass


class ArduinoDataError(PanError):
    """PanError raised when there is something very wrong with Arduino information."""
    pass


class MountNotFound(NotFound):

    """ Mount cannot be import """

    def __init__(self, msg='Mount Not Found'):
        super().__init__(msg, exit=True)


class CameraNotFound(NotFound):

    """ Camera cannot be imported """
    pass


class DomeNotFound(NotFound):
    """Dome device not found."""
    pass


class SolveError(NotFound):

    """ Camera cannot be imported """
    pass


class TheSkyXError(PanError):
    """ Errors from TheSkyX """
    pass


class TheSkyXKeyError(TheSkyXError):
    """ Errors from TheSkyX because bad key passed """
    pass


class TheSkyXTimeout(TheSkyXError):
    """ Errors from TheSkyX because bad key passed """
    pass


class GoogleCloudError(PanError):
    """ Errors related to google cloud """
    pass


class NotSupported(PanError, NotImplementedError):
    """ Errors from trying to use hardware features not supported by a particular model """
    pass


class IllegalValue(PanError, ValueError):
    """ Errors from trying to hardware parameters to values not supported by a particular model """
    pass

