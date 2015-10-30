import os
import shutil
import subprocess

from .. import has_logger
from .. import error


@has_logger
class PanIndiDevice(object):

    """ Interface to INDI for controlling hardware devices

    Convenience methods are provided for interacting with devices.

    Args:
        name(str):      Name for the device
        driver(str):    INDI driver to load
    """

    def __init__(self, name, driver, fifo='/tmp/pan_indiFIFO'):
        self.logger.info('Creating device {} ({})'.format(name, driver))

        self._getprop = shutil.which('indi_getprop')
        self._setprop = shutil.which('indi_setprop')

        assert self._getprop is not None, error.PanError("Can't find indi_getprop")
        assert self._setprop is not None, error.PanError("Can't find indi_setprop")

        self.name = name
        self.driver = driver

        self._fifo = fifo
        self._properties = {}

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_loaded(self):
        """ Tests if device driver is loaded on server. Catches the InvalidCommand error and returns False """
        loaded = False
        try:
            loaded = len(self.get_property(result=True)) > 0
        except error.FifoNotFound:
            self.logger.info("Fifo file not found. Unable to communicate with server.")
        except (AssertionError, error.InvalidCommand):
            self.logger.info("Device driver is not loaded. Unable to communicate with server.")

        return loaded

    @property
    def is_connected(self):
        """ Tests if device is connected. """
        connected = False
        if self.is_loaded:
            connected = self.get_property('CONNECTION', 'CONNECT')

        return connected

##################################################################################################
# Methods
##################################################################################################

    def get_property(self, property='*', element='*', result=True):
        """ Gets a property from a device

        Args:
            property(str):  Name of property. Defaults to '*'
            element(str):   Name of element. Defaults to '*'
            result(bool):   Parse response and return just result or output full
                response. Defaults to True (just the value).

        Returns:
            list(str) or str:      Output from the command. Either a list of lines or
                a single string.
        """
        assert os.path.exists(self._fifo), error.FifoNotFound("Can't get property")

        cmd = [self._getprop]
        if result:
            cmd.extend(['-1'])
        cmd.extend(['{}.{}.{}'.format(self.name, property, element)])

        self.logger.debug(cmd)

        output = ''
        try:
            output = subprocess.check_output(cmd, universal_newlines=True).strip().split('\n')
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand("Can't send command to server. {} \t {}".format(e, output))
        except Exception as e:
            raise error.PanError(e)

        return output

    def set_property(self, property, element, value):
        """ Sets a property from a device with a certain value

        Args:
            property(str):  Name of property.
            element(str):   Name of element.
            value(str):     Value for element.
        """
        cmd = [self._setprop]
        cmd.extend(['{}.{}.{}={}'.format(self.name, property, element, value)])
        self.logger.debug(cmd)

        output = ''
        try:
            output = subprocess.call(cmd)
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand(
                "Problem running indi command server. Does the server have valid drivers?")
        except Exception as e:
            raise error.InvalidCommand(e)

        return output

    def get_all_properties(self):
        """ Gets all the properties for all the devices
        Returns:
            dict:   Key value pairs of all properties for all devices
        """
        for item in self.get_property('*'):
            name, val = item.split('=')
            dev, prop, elem = name.split('.')
            self._properties[prop][elem] = val

        return self._properties

    def connect(self):
        """ Connect to device """
        self.set_property('CONNECTION', 'CONNECT', 'On')

    def disconnect(self):
        """ Connect to device """
        self.set_property('CONNECTION', 'Disconnect', 'On')
