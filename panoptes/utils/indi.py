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
        host(str):      Address for server to connect. Defaults to 'localhost'
        port(int):      Port for connection. Defaults to 7624.
        drivers(list):  List of valid drivers for indiserver to start. Defaults to ['indi_simulator_ccd']
    """

    def __init__(self, host='localhost', port=7624, drivers={'PAN_CCD_SIMULATOR': 'indi_simulator_ccd'}):
        self._indiserver = shutil.which('indiserver')

        assert self._indiserver is not None, PanError("Cannot find indiserver command")

        self.host = host
        self.port = port

        # Start the server
        self._fifo = None
        self._proc = self.start()

        self.load_drivers(drivers)

    def start(self, *args, **kwargs):
        """ Start an INDI server.

        Host, port, and drivers must be configured in advance.

        Returns:
            _proc(process):     Returns process from `subprocess.Popen`
        """
        # Add options
        fifo_name = kwargs.get('fifo_name', '/tmp/indiFIFO')

        try:
            if not os.path.exists(fifo_name):
                self._fifo = os.mkfifo(fifo_name)
            else:
                self._fifo = fifo_name
        except Exception as e:
            raise PanError("Can't open fifo at {} \t {}".format(fifo_name, e))

        cmd = [self._indiserver]

        opts = args if args else ['-v', '-m', '100', '-f', fifo_name]
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
        self.logger.debug("Shutting down INDI server (PID {})".format(self._proc.pid))
        self._proc.kill()

    def load_drivers(self, devices=[]):
        """ Load all the device drivers

        Args:
            devices(list):      A list of PanIndiDevice objects
        """
        # Load the drivers
        for device in devices:
            try:
                self.load_driver(device.driver, device.name)
            except error.InvalidCommand as e:
                self.logger.warning(
                    "Problem loading {} ({}) driver. Skipping for now.".format(device.name, device.driver))

    def load_driver(self, driver='indi_simulator_ccd', name=None):
        """ Loads a driver into the running server """

        cmd = ['start', driver]

        if name:
            cmd.extend(['-n', '\"{}\"'.format(name), '\n'])

        self._write_to_server(cmd)

    def unload_driver(self, driver='indi_simulator_ccd', name=None):
        """ Unloads a driver from the server """

        cmd = ['stop', driver]

        if name:
            cmd.extend(['\"{}\"'.format(name), '\n'])

        self._write_to_server(cmd)

    def _write_to_server(self, cmd):
        """ Write the command to the FIFO server """
        assert self._proc.pid, error.InvalidCommand("No running server found")

        str_cmd = ' '.join(cmd)
        self.logger.debug("Command to FIFO server: {}".format(str_cmd))
        try:
            with open(self._fifo, 'w') as f:
                f.write(str_cmd)
                f.flush()
                f.close()
        except:
            raise error.PanError("Problem writing to FIFO")


@has_logger
class PanIndiDevice(object):
    """ Interface to INDI for controlling hardware devices

    Convenience methods are provided for interacting with devices.
    """

    def __init__(self, name='PAN_CCD_SIMULATOR', driver='indi_simulator_ccd'):
        self.logger.info('Creating a PanIndiDevice')

        self._getprop = shutil.which('indi_getprop')
        self._setprop = shutil.which('indi_setprop')

        assert self._getprop is not None, PanError("Can't find indi_getprop")
        assert self._setprop is not None, PanError("Can't find indi_setprop")

        self.name = name
        self.driver = driver

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
        cmd = [self._getprop]
        if result:
            cmd.extend(['-1'])
        cmd.extend(['{}.{}.{}'.format(self.name, property, element)])

        self.logger.debug(cmd)

        output = ''
        try:
            output = subprocess.check_output(cmd, universal_newlines=True).strip().split('\n')
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand(
                "Problem running indi command server. Does the server have valid drivers?")
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
        cmd = [self._setprop, '{}.{}.{}={}'.format(self.name, property, element, value)]
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
        return {item.split('=')[0]: item.split('=')[0] for item in self.get_property('*')}

    def connect(self, device):
        """ Connect to device """
        self.set_property(device, 'CONNECTION', 'CONNECT', 'On')

    def disconnect(self, device):
        """ Connect to device """
        self.set_property(device, 'CONNECTION', 'Disconnect', 'On')
