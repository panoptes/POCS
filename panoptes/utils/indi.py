import os
import sys
import time
import shutil
import subprocess

from . import has_logger
from . import error

@has_logger
class PanIndiServer(object):
    """ A module to start an INDI server

    Args:
        drivers(dict):  Dict of valid drivers for indiserver to start, defaults to
            {'PAN_CCD_SIMULATOR': 'indi_simulator_ccd'}
        fifo(str):      Path to FIFO file of running indiserver
    """

    def __init__(self, drivers={'PAN_CCD_SIMULATOR': 'indi_simulator_ccd'}, fifo='/tmp/pan_indiFIFO'):
        self._indiserver = shutil.which('indiserver')

        assert self._indiserver is not None, PanError("Cannot find indiserver command")

        # Start the server
        self._fifo = fifo
        self._proc = self.start()

        if os.getpgid(self._proc.pid):
            self.load_drivers(drivers)

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_connected(self):
        """ INDI Server connection

        Tests whether running PID exists
        """
        return os.path.exists(os.path.join('proc',str(self._proc.pid)))

##################################################################################################
# Methods
##################################################################################################


    def start(self, *args, **kwargs):
        """ Start an INDI server.

        Host, port, and drivers must be configured in advance.

        Returns:
            _proc(process):     Returns process from `subprocess.Popen`
        """

        try:
            if not os.path.exists(self._fifo):
                os.mkfifo(self._fifo)
        except Exception as e:
            raise error.InvalidCommand("Can't open fifo at {} \t {}".format(fifo_name, e))

        cmd = [self._indiserver]

        opts = args if args else ['-v', '-m', '100', '-f', self._fifo]
        cmd.extend(opts)

        try:
            self.logger.debug("Starting INDI Server: {}".format(cmd))
            proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            self.logger.debug("INDI server started. PID: {}".format(proc.pid))
        except:
            self.logger.warning("Cannot start indiserver on {}:{}".format(self.host, self.port))
        return proc

    def stop(self):
        """ Stops the INDI server """
        if os.getpgid(self._proc.pid):
            self.logger.debug("Shutting down INDI server (PID {})".format(self._proc.pid))
            self._proc.kill()

        if os.path.exists(self._fifo):
            os.unlink(self._fifo)

    def load_drivers(self, devices={}):
        """ Load all the device drivers

        Args:
            devices(list):      A list of PanIndiDevice objects
        """
        # Load the drivers
        for dev_name, dev_driver in devices.items():
            try:
                self.load_driver(dev_name, dev_driver)
            except error.InvalidCommand as e:
                self.logger.warning(
                    "Problem loading {} ({}) driver. Skipping for now.".format(dev_name, dev_driver))

    def load_driver(self, name, driver):
        """ Loads a driver into the running server """
        self.logger.debug("Loading driver".format(driver))

        cmd = ['start', driver]

        if name:
            cmd.extend(['-n', '\"{}\"'.format(name), '\n'])

        self._write_to_server(cmd)

    def unload_driver(self, name, driver):
        """ Unloads a driver from the server """
        self.logger.debug("Unloading driver".format(driver))

        cmd = ['stop', driver]

        if name:
            cmd.extend(['\"{}\"'.format(name), '\n'])

        self._write_to_server(cmd)

##################################################################################################
# Private Methods
##################################################################################################

    def _write_to_server(self, cmd):
        """ Write the command to the FIFO server """
        assert self._proc.pid, error.InvalidCommand("No running server found")
        assert self._fifo, error.InvalidCommand("No FIFO file found")

        str_cmd = ' '.join(cmd)
        self.logger.debug("Command to FIFO server: {}".format(str_cmd))
        try:
            # I can't seem to get the FIFO to work without the explicit flush and close
            with open(self._fifo, 'w') as f:
                f.write(str_cmd)
                f.flush()
                f.close()
        except Exception as e:
            raise error.PanError("Problem writing to FIFO: {}".format(e))

    def __del__(self):
        self.stop()

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

        assert self._getprop is not None, PanError("Can't find indi_getprop")
        assert self._setprop is not None, PanError("Can't find indi_setprop")

        self.name = name
        self.driver = driver

        self._fifo = fifo

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_loaded(self):
        """ Tests if device driver is loaded on server. Catches the InvalidCommand error and returns False """
        loaded = False
        try:
            loaded = len(self.get_property(result=False)) > 0
        except error.FifoNotFound as e:
            self.logger.info("Fifo file not found. Unable to communicate with server.")
        except (AssertionError, error.InvalidCommand):
            self.logger.info("Device driver is not loaded. Unable to communicate with server.")

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

        cmd = [self._getprop, '-d', self._fifo]
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
            raise PanError(e)

        return output

    def set_property(self, property, element, value):
        """ Sets a property from a device with a certain value

        Args:
            property(str):  Name of property.
            element(str):   Name of element.
            value(str):     Value for element.
        """
        cmd = [self._setprop, '-d', self._fifo]
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
        return {item.split('=')[0]: item.split('=')[1] for item in self.get_property('*')}

    def connect(self):
        """ Connect to device """
        self.set_property('CONNECTION', 'CONNECT', 'On')

    def disconnect(self):
        """ Connect to device """
        self.set_property('CONNECTION', 'Disconnect', 'On')
