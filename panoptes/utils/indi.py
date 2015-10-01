import os
import sys
import time
import PyIndi

from . import has_logger
from . import NotFound

switch_lookup = {
    PyIndi.ISS_OFF:  "Off",
    PyIndi.ISS_ON:  "On",
}

state_lookup = {
    PyIndi.IPS_IDLE:  "Idle",
    PyIndi.IPS_OK:  "Ok",
    PyIndi.IPS_BUSY:  "Busy",
    PyIndi.IPS_ALERT:  "Alert",
}

type_lookup = {
    PyIndi.INDI_TEXT: 'text',
    PyIndi.INDI_NUMBER: 'number',
    PyIndi.INDI_SWITCH: 'switch',
    PyIndi.INDI_LIGHT: 'light',
    PyIndi.INDI_BLOB: 'blob',
}


@has_logger
class PanIndi(PyIndi.BaseClient):

    def __init__(self, host='localhost', port=7624):
        super().__init__()
        self.logger.info('Creating an instance of PanIndi')

        self.host = host
        self.port = port
        self.setServer(host, port)

        self.devices = {}

        if (self.connect()):
            self.logger.info("Connected to indi server")
            # self.get_devices()

    def connect(self, wait=1):
        """ Connect to the server """
        self.logger.info("Connecting to server and waiting {} secs".format(wait))

        connected = False
        try:
            connected = self.connectServer()
        except:
            cmd = "indiserver indi_simulator_telescope indi_simulator_ccd"
            msg = "No indiserver running on {}: Try to run \n {}".format(self.host, self.port, cmd)
            raise NotFound(msg, exit=True)
        else:
            time.sleep(wait)
            self.logger.info("Connected")

        return connected

    def newDevice(self, d):
        """ Add a new device to list

        Checks first to make sure item is not already in list

        NOTE:
            What about multiple devices? This is just storing the driver name
        """
        name = d.getDeviceName()
        self.logger.info("New device: {}".format(name))
        if name not in self.devices:
            self.devices[name] = d

    def newProperty(self, p):
        self.logger.debug("newProperty on {}: {}".format(p.getDeviceName(), p.getName()))

    def removeProperty(self, p):
        self.logger.debug("removeProperty on {}: {}".format(p.getDeviceName(), p.getName()))

    def newBLOB(self, bp):
        self.logger.info("new BLOB " + bp.name)

        img = bp.getblobdata()

        with open("frame.fit", "wb") as f:
            f.write(img)

    def newSwitch(self, svp):
        self.logger.debug("newSwitch on {}: {} \t {}".format(svp.device, svp.name, svp.nsp))

    def newNumber(self, nvp):
        self.logger.debug("newNumber on {}: {} \t {}".format(nvp.device, nvp.name, nvp.nnp))

    def newText(self, tvp):
        self.logger.debug("newText on {}: {} \t {}".format(tvp.device, tvp.name, tvp.ntp))

    def newLight(self, lvp):
        self.logger.debug("newText on {}: {} \t {}".format(lvp.device, lvp.name, lvp.nlp))

    def newMessage(self, d, m):
        self.logger.debug("newMessage on {}: \t {}".format(d.getDeviceName(), d.messageQueue(m)))

    def serverConnected(self):
        self.logger.debug("serverConnected on {}:{}".format(self.getHost(), self.getPort()))

    def serverDisconnected(self, code):
        self.logger.debug("serverDisconnected on {}:{}. Reason: {}".format(self.getHost(), self.getPort(), code))

    def load_devices(self):
        """ Loads the devices from the indiserve and stores them locally """
        for dev in self.getDevices():
            name = dev.getDeviceName()
            if name not in self.devices:
                self.devices[name] = dev

    def list_device_properties(self, device):
        self.logger.info("Getting properties for {}".format(device.getDeviceName()))
        for prop in device.getProperties():
            prop_name = prop.getName()
            prop_type = prop.getType()

            if prop_type == PyIndi.INDI_TEXT:
                tpy = prop.getText()
                for t in tpy:
                    self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.text))
            elif prop_type == PyIndi.INDI_NUMBER:
                tpy = prop.getNumber()
                for t in tpy:
                    self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.value))
            elif prop_type == PyIndi.INDI_SWITCH:
                tpy = prop.getSwitch()
                for t in tpy:
                    self.logger.debug("{} ({}) \t {}".format(t.name, t.label, switch_lookup.get(t.s)))
            elif prop_type == PyIndi.INDI_LIGHT:
                tpy = prop.getLight()
                for t in tpy:
                    self.logger.debug("{} ({}) \t {}".format(t.name, t.label, state_lookup.get(t.s)))
            elif prop_type == PyIndi.INDI_BLOB:
                tpy = prop.getBLOB()
                for t in tpy:
                    self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.size))

    def get_property_value(self, device=None, prop=None, elem=None):
        """ Puts the property value into a sane format depending on type """
        assert device is not None
        self.logger.debug("{}: {}".format("device",device))
        self.logger.debug("{}: {}".format("prop",prop))
        self.logger.debug("{}: {}".format("elem",elem))

        # If we have a string, try to load property
        if isinstance(prop, str):
            self.logger.info("Looking up property: {} on {}".format(prop, device))
            device = self.getDevice(device)
            prop = device.getProperty(prop)
            self.logger.info("Property: {}".format(prop))

        assert prop is not None

        prop_name = prop.getName()
        prop_type = prop.getType()
        prop_value = []

        self.logger.info("'{}' type: {}".format(prop_name, type_lookup.get(prop_type)))

        if prop_type == PyIndi.INDI_TEXT:
            tpy = prop.getText()
            for t in tpy:
                self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.text))
                if elem is None or elem == t.name:
                    prop_value.append((t.label, t.text))
        elif prop_type == PyIndi.INDI_NUMBER:
            tpy = prop.getNumber()
            for t in tpy:
                self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.value))
                if elem is None or elem == t.name:
                    prop_value.append((t.label, t.value))
        elif prop_type == PyIndi.INDI_SWITCH:
            tpy = prop.getSwitch()
            print(tpy)
            for t in tpy:
                self.logger.debug("{} ({}) \t {}".format(t.name, t.label, switch_lookup.get(t.s)))
                if elem is None or elem == t.name:
                    prop_value.append((t.label, switch_lookup.get(t.s, 'UNKNOWN')))
        elif prop_type == PyIndi.INDI_LIGHT:
            tpy = prop.getLight()
            for t in tpy:
                self.logger.debug("{} ({}) \t {}".format(t.name, t.label, state_lookup.get(t.s)))
                if elem is None or elem == t.name:
                    prop_value.append((t.label, state_lookup.get(t.s, 'UNKNOWN')))
        elif prop_type == PyIndi.INDI_BLOB:
            tpy = prop.getBLOB()
            for t in tpy:
                self.logger.debug("{} ({}) \t {}".format(t.name, t.label, t.size))
                if elem is None or elem == t.name:
                    prop_value.append((t.label, t.size))

        return prop_value
