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

        # Load the drivers
        for name, driver in drivers.items():
            try:
                self.load_driver(driver, name)
            except error.InvalidCommand as e:
                self.logger.warning(
                    "Problem loading {} ({}) driver. Skipping for now.".format(name, driver))

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
    """ Object representing an INDI device """

    def __init__(self, name):
        self.name = name
        self.logger.debug("Connectiong INDI device {}".format(self.name))


@has_logger
class PanIndi(object):
    """ Interface to INDI for controlling hardware

    This module is capable of both spawning a server as well as connecting
    a client. Convenience methods are provided for interacting with devices.

    """

    def __init__(self, host='localhost', port=7624, devices={'PAN_CCD_SIMULATOR': {'driver': 'indi_simulator_ccd'}}):
        self.logger.info('Creating an instance of PanIndi')

        self.host = host
        self.port = port

        drivers = {dev_name: dev_config['driver'] for dev_name, dev_config in devices.items()}

        self.server = PanIndiServer(self.host, self.port, drivers)

        self._getprop = shutil.which('indi_getprop')
        self._setprop = shutil.which('indi_setprop')

        assert self._getprop is not None, PanError("Can't find indi_getprop")
        assert self._setprop is not None, PanError("Can't find indi_setprop")

        self.devices = {}
        # self._load_devices()

    def get_property(self, device, property='*', element='*'):
        """ Gets a property from a device

        Args:
            device(str):    Name of device.
            property(str):  Name of property. Defaults to '*'
            element(str):   Name of element. Defaults to '*'
        """
        cmd = [self._getprop, '{}.{}.{}'.format(device, property, element)]
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

    def get_all(self):
        """ Gets all the properties for all the devices
        Returns:
            dict:   Key value pairs of all properties for all devices
        """
        return {item.split('=')[0]: item.split('=')[0] for item in self.get_property('*')}

    def _load_devices(self):
        """ Loads the devices from the indiserve and stores them locally """
        devices = set(key.split('.')[0] for key in self.get_all().keys())

        for device in devices:
            self.devices[device] = PanIndiDevice(device)

    # def connect(self, wait=1):
    #     """ Connect to the server """
    #     self.logger.info("Connecting to server and waiting {} secs".format(wait))
    #
    #     connected = False
    #     try:
    #         connected = self.connectServer()
    #     except:
    #         cmd = "indiserver indi_simulator_telescope indi_simulator_ccd"
    #         msg = "No indiserver running on {}: Try to run \n {}".format(self.host, self.port, cmd)
    #         raise error.NotFound(msg, exit=True)
    #     else:
    #         time.sleep(wait)
    #         self.logger.info("Connected")
    #
    #     return connected
    #
    # def newDevice(self, d):
    #     """ Add a new device to list
    #
    #     Checks first to make sure item is not already in list
    #
    #     NOTE:
    #         What about multiple devices? This is just storing the driver name
    #     """
    #     name = d.getDeviceName()
    #     self.logger.info("New device: {}".format(name))
    #     if name not in self.devices:
    #         self.devices[name] = d
    #
    # def newProperty(self, p):
    #     self.logger.debug("newProperty on {}: {}".format(p.getDeviceName(), p.getName()))
    #
    # def removeProperty(self, p):
    #     self.logger.debug("removeProperty on {}: {}".format(p.getDeviceName(), p.getName()))
    #
    # def newBLOB(self, bp):
    #     self.logger.info("new BLOB " + bp.name)
    #
    #     img = bp.getblobdata()
    #
    #     with open("frame.fit", "wb") as f:
    #         f.write(img)
    #
    # def newSwitch(self, svp):
    #     self.logger.debug("newSwitch on {}: {} \t {}".format(svp.device, svp.name, svp.nsp))
    #
    # def newNumber(self, nvp):
    #     self.logger.debug("newNumber on {}: {} \t {}".format(nvp.device, nvp.name, nvp.nnp))
    #
    # def newText(self, tvp):
    #     self.logger.debug("newText on {}: {} \t {}".format(tvp.device, tvp.name, tvp.ntp))
    #
    # def newLight(self, lvp):
    #     self.logger.debug("newText on {}: {} \t {}".format(lvp.device, lvp.name, lvp.nlp))
    #
    # def newMessage(self, d, m):
    #     self.logger.debug("newMessage on {}: \t {}".format(d.getDeviceName(), d.messageQueue(m)))
    #
    # def serverConnected(self):
    #     self.logger.debug("serverConnected on {}:{}".format(self.getHost(), self.getPort()))
    #
    # def serverDisconnected(self, code):
    #     self.logger.debug("serverDisconnected on {}:{}. Reason: {}".format(self.getHost(), self.getPort(), code))

    # def list_device_properties(self, device):
    #     self.logger.info("Getting properties for {}".format(device.getDeviceName()))
    #     for prop in device.getProperties():
    #         prop_name = prop.getName()
    #         prop_type = prop.getType()
    #
    #         if prop_type == PyIndi.INDI_TEXT:
    #             tpy = prop.getText()
    #             for t in tpy:
    #                 self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.text))
    #         elif prop_type == PyIndi.INDI_NUMBER:
    #             tpy = prop.getNumber()
    #             for t in tpy:
    #                 self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.value))
    #         elif prop_type == PyIndi.INDI_SWITCH:
    #             tpy = prop.getSwitch()
    #             for t in tpy:
    #                 self.logger.debug("{} ({}) \t {}".format(t.name, t.label, switch_lookup.get(t.s)))
    #         elif prop_type == PyIndi.INDI_LIGHT:
    #             tpy = prop.getLight()
    #             for t in tpy:
    #                 self.logger.debug("{} ({}) \t {}".format(t.name, t.label, state_lookup.get(t.s)))
    #         elif prop_type == PyIndi.INDI_BLOB:
    #             tpy = prop.getBLOB()
    #             for t in tpy:
    #                 self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.size))
    #
    # def check_device(self, device=None):
    #     pass
    #
    # def get_property_value(self, device=None, prop=None, elem=None):
    #     """ Puts the property value into a sane format depending on type """
    #     assert device is not None
    #     self.logger.debug("{}: {}".format("device",device))
    #     self.logger.debug("{}: {}".format("prop",prop))
    #     self.logger.debug("{}: {}".format("elem",elem))
    #
    #     # If we have a string, try to load property
    #     if isinstance(prop, str):
    #         self.logger.info("Looking up property: {} on {}".format(prop, device))
    #         device = self.getDevice(device)
    #         prop = device.getProperty(prop)
    #         self.logger.info("Property: {}".format(prop))
    #
    #     assert prop is not None
    #
    #     prop_name = prop.getName()
    #     prop_type = prop.getType()
    #     prop_value = []
    #
    #     self.logger.info("'{}' type: {}".format(prop_name, type_lookup.get(prop_type)))
    #
    #     if prop_type == PyIndi.INDI_TEXT:
    #         tpy = prop.getText()
    #         for t in tpy:
    #             self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.text))
    #             if elem is None or elem == t.name:
    #                 prop_value.append((t.label, t.text))
    #     elif prop_type == PyIndi.INDI_NUMBER:
    #         tpy = prop.getNumber()
    #         for t in tpy:
    #             self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.value))
    #             if elem is None or elem == t.name:
    #                 prop_value.append((t.label, t.value))
    #     elif prop_type == PyIndi.INDI_SWITCH:
    #         tpy = prop.getSwitch()
    #         print(tpy)
    #         for t in tpy:
    #             self.logger.debug("{} ({}) \t {}".format(t.name, t.label, switch_lookup.get(t.s)))
    #             if elem is None or elem == t.name:
    #                 prop_value.append((t.label, switch_lookup.get(t.s, 'UNKNOWN')))
    #     elif prop_type == PyIndi.INDI_LIGHT:
    #         tpy = prop.getLight()
    #         for t in tpy:
    #             self.logger.debug("{} ({}) \t {}".format(t.name, t.label, state_lookup.get(t.s)))
    #             if elem is None or elem == t.name:
    #                 prop_value.append((t.label, state_lookup.get(t.s, 'UNKNOWN')))
    #     elif prop_type == PyIndi.INDI_BLOB:
    #         tpy = prop.getBLOB()
    #         for t in tpy:
    #             self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.size))
    #             if elem is None or elem == t.name:
    #                 prop_value.append((t.label, t.size))
    #
    #     return prop_value
