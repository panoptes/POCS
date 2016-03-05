import shutil
import subprocess

from ..logger import get_logger
from .. import error
from .. import listify


class PanIndiDevice(object):

    """ Interface to INDI for controlling hardware devices

    Convenience methods are provided for interacting with devices.

    Args:
        name(str):      Name for the device
        driver(str):    INDI driver to load
    """

    def __init__(self, config, **kwargs):
        super(PanIndiDevice, self).__init__(config, **kwargs)

        self.logger = get_logger(self)
        name = 'iEQ'
        driver = config.get('driver', 'indi_simulator_ccd')
        port = config.get('port')

        self.logger.info('Creating device {} ({})'.format(name, driver))

        self._getprop = shutil.which('indi_getprop')
        self._setprop = shutil.which('indi_setprop')

        assert self._getprop is not None, error.PanError("Can't find indi_getprop")
        assert self._setprop is not None, error.PanError("Can't find indi_setprop")

        self.name = name
        self.driver = driver
        self.port = port

        self.status_delay = kwargs.get('status_delay', 1.3)  # Why not
        self._status_thread = None

        self._driver_loaded = False
        self._properties = {}
        self._states = {}

        self.config = config

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_loaded(self):
        """ Tests if device driver is loaded on server. Catches the InvalidCommand error and returns False """
        if not self._driver_loaded:
            try:
                self._driver_loaded = len(self.get_property()) > 0
            except (AssertionError, error.InvalidCommand):
                self.logger.info("Device driver is not loaded. Unable to communicate with server.")

        return self._driver_loaded

    @property
    def is_connected(self):
        """ Tests if device is connected. """
        connected = False

        # if self.is_loaded:
        try:
            if self.get_property('CONNECTION', 'CONNECT', result=True) == 'On':
                connected = True
        except error.InvalidCommand:
            self.logger.debug("{} not connected".format(self.name))

        return connected

    @property
    def properties(self):
        return self._properties

    @property
    def states(self):
        return self._states


##################################################################################################
# Methods
##################################################################################################

    def lookup_properties(self, switched_on_only=False):
        """ Gets all the properties for all the devices

        Returns:
            dict:   Key value pairs of all properties for all devices
        """
        new_properties = {}
        new_states = {}

        # self.logger.debug("Looking up properties from device")
        for item in self.get_property('*'):
            name, val = item.split('=', maxsplit=1)
            dev, prop, elem = name.split('.')

            # Add values to an array
            if val in ['On', 'Off'] and switched_on_only:
                if val == 'On':
                    new_properties.setdefault(prop, elem)
            else:
                if prop in new_properties:
                    new_properties[prop][elem] = val
                else:
                    new_properties.setdefault(prop, {elem: val})

            state = self.get_state(prop)
            if prop in new_states:
                new_states[prop] = state
            else:
                new_states.setdefault(prop, state)

        # If nothing returned then no driver
        if len(new_properties) == 0:
            self._driver_loaded = False

        self._properties = new_properties
        self._states = new_states

    def get_state(self, property_name='*', **kwargs):
        state = self.get_property(property_name=property_name, element='_STATE', result=True, **kwargs)
        # self.logger.debug('State: {} {}'.format(property_name, state))

        return state

    def get_property(self, property_name='*', element='*', result=False, verbose=False):
        """ Gets a property_name from a device

        Args:
            property_name(str):  Name of property_name. Defaults to '*'
            element(str):   Name of element. Defaults to '*'
            result(bool):   Parse response and return just result or output full
                response. Defaults to True (just the value).

        Returns:
            list(str) or str:      Output from the command. Either a list of lines or
                a single string.
        """

        cmd = [self._getprop]
        if verbose:
            cmd.extend(['-vv'])
        if result:
            cmd.extend(['-1'])

        cmd.extend(['{}.{}.{}'.format(self.name, property_name, element)])

        output = ''
        try:
            output = subprocess.check_output(cmd, universal_newlines=True).strip().split('\n')
            if isinstance(output, int):
                if output > 0:
                    raise error.InvalidCommand("Problem with get_property. Output: {}".format(output))
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand("Can't send command to server. {} \t {}".format(e, output))
        except Exception as e:
            raise error.PanError(e)

        if not result:
            output = list(set(listify(output)))
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

        self.logger.debug("elem_values: {}".format(elem_values))

        elems = ";".join(elem_values.keys())
        vals = ";".join(elem_values.values())

        cmd.extend(["{}.{}.{}={}".format(self.name, prop, elems, vals)])

        self.logger.debug("{} command: {}".format(self.name, cmd))

        output = ''
        try:
            output = subprocess.call(cmd)
            self.logger.debug("Output from set_property: {}".format(output))
            if output > 0:
                raise error.InvalidCommand("Problem with set_property. \n Cmd{} \n Output: {}".format(cmd, output))
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand(
                "Problem running indi command server. Does the server have valid drivers?")
        except Exception as e:
            raise error.InvalidCommand(e)

        return output

    def connect(self):
        """ Connect to device """
        self.logger.debug('Connecting {}'.format(self.name))

        if 'simulator' in self.config:
            self.set_property('SIMULATION', {'ENABLE': 'On', 'DISABLE': 'Off'})
        else:
            self.set_property('SIMULATION', {'ENABLE': 'Off', 'DISABLE': 'On'})

        if self.driver == 'indi_ieq_telescope':
            self.set_property('DEVICE_PORT', {'PORT': self.port})
        elif self.driver == 'indi_gphoto_ccd':
            self.set_property('SHUTTER_PORT', {'PORT': self.port})

        # Zero is success
        if self.set_property('CONNECTION', {'CONNECT': 'On'}) == 0:
            self.logger.debug('{} connected'.format(self.name))

            # Run through the initialization commands if present
            if self.config.get('init_commands'):
                self.logger.debug('Setting initial properties for {}'.format(self.name))

                for prop, elem in self.config.get('init_commands').items():
                    self.set_property(prop, elem)

            self.logger.debug('Getting properties for {}'.format(self.name))
        else:
            self.logger.warning("Can't connect to {}".format(self.name))

    def disconnect(self):
        """ Connect to device """
        self.logger.debug('Disconnecting {}'.format(self.name))
        self.set_property('CONNECTION', {'Disconnect': 'On'})

##################################################################################################
# Private Methods
##################################################################################################
