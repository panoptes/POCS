import re
import yaml
import subprocess
import os
import datetime

from . import AbstractCamera

from ..utils.logger import has_logger
from ..utils.config import load_config
from ..utils.indi import PanIndiDevice

@has_logger
class Camera(AbstractCamera, PanIndiDevice):

    def __init__(self, device_name, config=dict(), *args, **kwargs):
        super().__init__(name=device_name, config=config, *args, **kwargs)

        self.last_start_time = None

    def init(self):

        self.logger.info("Setting defaults for camera")
        self.get_serial_number()

        self.client.get_property_value(self.name, 'UPLOAD_MODE')
        # self.client.sendNewText(self.name, 'UPLOAD_MODE', 'Local', 'On')
        self.client.sendNewSwitch(self.name, 'CCD_ISO', 'ISO1')
        # result = self.set('Auto Power Off', 0)     # Don't power off
        # result = self.set('/main/settings/reviewtime', 0)       # Screen off
        # result = self.set('/main/settings/capturetarget', 1)    # SD Card
        # result = self.set('/main/settings/ownername', 'Project PANOPTES')
        # result = self.set('/main/settings/copyright', 'Project PANOPTES 2015')
        #
        # result = self.set('/main/status/lensname', 'Rokinon 85mm')
        #
        # result = self.set('/main/imgsettings/imageformat', 9)       # RAW
        # result = self.set('/main/imgsettings/imageformatsd', 9)     # RAW
        # result = self.set('/main/imgsettings/imageformatcf', 9)     # RAW
        # result = self.set('/main/imgsettings/iso', 1)               # ISO 100
        # result = self.set('/main/imgsettings/colorspace', 0)        # sRGB
        #
        # result = self.set('/main/capturesettings/focusmode', 0)         # Manual
        # result = self.set('/main/capturesettings/autoexposuremode', 3)  # 3 - Manual; 4 - Bulb
        # result = self.set('/main/capturesettings/drivemode', 0)         # Single exposure
        # result = self.set('/main/capturesettings/picturestyle', 1)      # Standard
        #
        # result = self.set('/main/capturesettings/shutterspeed', 0)      # Bulb
        #
        # result = self.set('/main/actions/syncdatetime', 1)  # Sync date and time to computer
        # result = self.set('/main/actions/uilock', 1)        # Don't let the UI change
        #
        # # Get Camera Properties

    def connect(self):
        '''
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        '''
        self.logger.info('Connecting to camera')

        # connect to device
        if self.client.connect():
            self.client.connectDevice(self.device.getDeviceName())
            self.client.get_property_value(self.name, 'CONNECTION')

            # set BLOB mode to BLOB_ALSO
            self.client.setBLOBMode(1, self.name, None)

            self.logger.info("Connected to camera")
            self.init()
        else:
            self.logger.warning("Problem connecting to indiserver")

    def start_cooling(self):
        '''
        This does nothing for a Canon DSLR as it does not have cooling.
        '''
        self.logger.info('No camera cooling available')
        self.cooling = True

    def stop_cooling(self):
        '''
        This does nothing for a Canon DSLR as it does not have cooling.
        '''
        self.logger.info('No camera cooling available')
        self.cooling = False

    def construct_filename(self):
        '''
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        '''
        if self.last_start_time:
            filename = self.last_start_time.strftime('{}_%Y%m%dat%H%M%S.cr2'.format(self.name))
        else:
            filename = self.last_start_time.strftime('image.cr2')
        return filename

    def take_exposure(self, exptime=5):
        """ Take an exposure """
        self.logger.info("<<<<<<<< Exposure >>>>>>>>>")
        self.logger.info('Taking {} second exposure'.format(exptime))

        self.last_start_time = datetime.datetime.now()

        # get current exposure time
        exp = self.device.getNumber("CCD_EXPOSURE")
        # set exposure time to 5 seconds
        exp[0].value = exptime
        # send new exposure time to server/device
        self.client.sendNewNumber(exp)
        self.logger.debug("Exposre command sent to camera")


# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------
