import PyIndi
import time
from . import has_logger

def strISState(s):
    if (s == PyIndi.ISS_OFF):
        return "Off"
    else:
        return "On"

def strIPState(s):
    if (s == PyIndi.IPS_IDLE):
        return "Idle"
    elif (s == PyIndi.IPS_OK):
        return "Ok"
    elif (s == PyIndi.IPS_BUSY):
        return "Busy"
    elif (s == PyIndi.IPS_ALERT):
        return "Alert"

@has_logger
class PanIndi(PyIndi.BaseClient):
    def __init__(self, host='localhost', port=7624):
        super().__init__()
        self.logger.info('Creating an instance of PanIndi')

        self.host = host
        self.port = port
        self.setServer(host,port)

        if (self.connect()):
            self.devices = self.get_devices()


    def connect(self):
        """ Connect to the server """
        self.logger.info("Connecting and waiting 2secs")
        connected = True if self.connectServer() else False
        if (not connected):
             self.logger.warning("No indiserver running on "+self.host+":"+str(self.port)+" - Try to run")
             self.logger.warning("  indiserver indi_simulator_telescope indi_simulator_ccd")
             sys.exit(1)
        else:
            time.sleep(1)

        return connected

    def newDevice(self, d):
        self.logger.info("new device " + d.getDeviceName())
        #self.logger.info("new device ")
    def newProperty(self, p):
        self.logger.info("new property "+ p.getName() + " for device "+ p.getDeviceName())
        #self.logger.info("new property ")
    def removeProperty(self, p):
        self.logger.info("remove property "+ p.getName() + " for device "+ p.getDeviceName())
    def newBLOB(self, bp):
        self.logger.info("new BLOB "+ bp.name)
    def newSwitch(self, svp):
        self.logger.info ("new Switch "+ svp.name + " for device "+ svp.device)
    def newNumber(self, nvp):
        self.logger.info("new Number "+ nvp.name + " for device "+ nvp.device)
    def newText(self, tvp):
        self.logger.info("new Text "+ tvp.name + " for device "+ tvp.device)
    def newLight(self, lvp):
        self.logger.info("new Light "+ lvp.name + " for device "+ lvp.device)
    def newMessage(self, d, m):
        self.logger.info("new Message "+ d.messageQueue(m))
    def serverConnected(self):
        self.logger.info("Server connected ("+self.getHost()+":"+str(self.getPort())+")")
    def serverDisconnected(self, code):
        self.logger.info("Server disconnected (exit code = "+str(code)+","+str(self.getHost())+":"+str(self.getPort())+")")

    def get_devices(self):
        """ Loads the devices from the indiserve and stores them locally """
        devs = {dev.getDeviceName():dev for dev in self.getDevices()}
        return devs

    def list_device_properties(self, device):
        self.logger.info("Getting properties for {}".format(device.getDeviceName()))
        for prop in device.getProperties():
            prop_name = prop.getName()
            prop_type = prop.getType()

            if prop_type==PyIndi.INDI_TEXT:
                tpy=prop.getText()
                for t in tpy:
                    self.logger.info("       "+t.name+"("+t.label+")= "+t.text)
            elif prop_type==PyIndi.INDI_NUMBER:
                tpy=prop.getNumber()
                for t in tpy:
                    self.logger.info("       "+t.name+"("+t.label+")= "+str(t.value))
            elif prop_type==PyIndi.INDI_SWITCH:
                tpy=prop.getSwitch()
                for t in tpy:
                    self.logger.info("       "+t.name+"("+t.label+")= "+strISState(t.s))
            elif prop_type==PyIndi.INDI_LIGHT:
                tpy=prop.getLight()
                for t in tpy:
                    self.logger.info("       "+t.name+"("+t.label+")= "+strIPState(t.s))
            elif prop_type==PyIndi.INDI_BLOB:
                tpy=prop.getBLOB()
                for t in tpy:
                    self.logger.info("       "+t.name+"("+t.label+")= <blob "+str(t.size)+" bytes>")
