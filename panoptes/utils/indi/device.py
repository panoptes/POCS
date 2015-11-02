import os
import shutil
import subprocess

from .. import has_logger
from .. import error
from .. import listify


@has_logger
class PanIndiDevice(object):

    """ Interface to INDI for controlling hardware devices

    Convenience methods are provided for interacting with devices.

    Args:
        name(str):      Name for the device
        driver(str):    INDI driver to load
    """

    def __init__(self, config={}, fifo='/tmp/pan_indiFIFO'):
        name = config.get('name', 'Generic PanIndiDevice')
        driver = config.get('driver', 'indi_simulator_ccd')

        self.logger.info('Creating device {} ({})'.format(name, driver))

        # Check the config for required items
        # assert config.get('port') is not None, self.logger.error(
        #     'No port specified, cannot create PanIndiDevice\n {}'.format(config))

        self._getprop = shutil.which('indi_getprop')
        self._setprop = shutil.which('indi_setprop')

        assert self._getprop is not None, error.PanError("Can't find indi_getprop")
        assert self._setprop is not None, error.PanError("Can't find indi_setprop")

        self.name = name
        self.driver = driver

        self._fifo = fifo
        self._properties = {}

        self.config = config

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_loaded(self):
        """ Tests if device driver is loaded on server. Catches the InvalidCommand error and returns False """
        loaded = False
        try:
            loaded = len(self.get_property()) > 0
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
            try:
                connected = self.get_property('CONNECTION', 'CONNECT')
            except error.InvalidCommand:
                self.logger.debug("{} not connected".format(self.name))

        return connected

##################################################################################################
# Methods
##################################################################################################
    def get_all_properties(self):
        """ Gets all the properties for all the devices

        Returns:
            dict:   Key value pairs of all properties for all devices
        """
        for item in self.get_property('*'):
            name, val = item.split('=', maxsplit=1)
            dev, prop, elem = name.split('.')

            if prop in self._properties:
                self._properties[prop][elem] = val
            else:
                self._properties.setdefault(prop, {elem: val})

        return self._properties

    def get_property(self, property='*', element='*', result=False, verbose=False):
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
        if verbose:
            cmd.extend(['-vv'])
        if result:
            cmd.extend(['-1'])

        cmd.extend(['{}.{}.{}'.format(self.name, property, element)])

        self.logger.debug(cmd)

        output = ''
        try:
            output = subprocess.check_output(cmd, universal_newlines=True).strip().split('\n')
            self.logger.info("Output: {} {}".format(output, type(output)))
            if isinstance(output, int):
                if output > 0:
                    raise error.InvalidCommand("Problem with get_property. Output: {}".format(output))
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand("Can't send command to server. {} \t {}".format(e, output))
        except Exception as e:
            raise error.PanError(e)

        if not result:
            output = listify(output)
        else:
            output = output[0]

        return output

    def set_property(self, prop, elem_values, verbose=False):
        """ Sets a property from a device with a certain value

        Args:
            prop(str):              Name of property.
            elem_values(List[dict]):    List of (key, value) pairs for properties to set.
        """
        cmd = [self._setprop]
        if verbose:
            cmd.extend(['-vv'])

        elems = ";".join(elem_values.keys())
        vals = ";".join(elem_values.values())

        cmd.extend(["{}.{}.{}={}".format(self.name, prop, elems, vals)])

        self.logger.debug("{} command: {}".format(self.name, cmd))

        output = ''
        try:
            output = subprocess.call(cmd)
            self.logger.debug("Output from set_property: {}".format(output))
            if output > 0:
                raise error.InvalidCommand("Problem with set_property. Output: {}".format(output))
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand(
                "Problem running indi command server. Does the server have valid drivers?")
        except Exception as e:
            raise error.InvalidCommand(e)

        return output

    def connect(self):
        """ Connect to device """
        self.logger.debug('Connecting {}'.format(self.name))

        # Zero is success
        if self.set_property('CONNECTION', {'CONNECT': 'On'}) == 0:
            self.logger.debug('{} connected'.format(self.name))

            # Run through the initialization commands if present
            if self.config.get('init_commands'):
                self.logger.debug('Setting initial properties for {}'.format(self.name))

                for prop, elem in self.config.get('init_commands').items():
                    self.set_property(prop, elem)

            self.logger.debug('Getting properties for {}'.format(self.name))
        # self.get_all_properties()
        else:
            self.logger.warning("Can't connect to {}".format(self.name))

    def disconnect(self):
        """ Connect to device """
        self.logger.debug('Disconnecting {}'.format(self.name))
        self.set_property('CONNECTION', {'Disconnect': 'On'})
