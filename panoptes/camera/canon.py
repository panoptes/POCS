# Note Mac users may need to kill a process to claim camera with gphoto:
# killall PTPCamera

import re
import yaml
import subprocess
import os
import datetime

from . import AbstractCamera

from ..utils.logger import has_logger
from ..utils.config import load_config


@has_logger
class Camera(AbstractCamera):

    def __init__(self, config=dict(), *args, **kwargs):
        super().__init__(config=config, *args, **kwargs)

        self.last_start_time = None


    def connect(self):
        '''
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        '''
        self.logger.info('Connecting to camera')
        self.load_properties()

        result = self.set('Auto Power Off', 0)     # Don't power off
        result = self.set('/main/settings/reviewtime', 0)       # Screen off
        result = self.set('/main/settings/capturetarget', 1)    # SD Card
        result = self.set('/main/settings/ownername', 'Project PANOPTES')
        result = self.set('/main/settings/copyright', 'Project PANOPTES 2015')

        result = self.set('/main/status/lensname', 'Rokinon 85mm')

        result = self.set('/main/imgsettings/imageformat', 9)       # RAW
        result = self.set('/main/imgsettings/imageformatsd', 9)     # RAW
        result = self.set('/main/imgsettings/imageformatcf', 9)     # RAW
        result = self.set('/main/imgsettings/iso', 1)               # ISO 100
        result = self.set('/main/imgsettings/colorspace', 0)        # sRGB

        result = self.set('/main/capturesettings/focusmode', 0)         # Manual
        result = self.set('/main/capturesettings/autoexposuremode', 3)  # 3 - Manual; 4 - Bulb
        result = self.set('/main/capturesettings/drivemode', 0)         # Single exposure
        result = self.set('/main/capturesettings/picturestyle', 1)      # Standard

        result = self.set('/main/capturesettings/shutterspeed', 0)      # Bulb

        result = self.set('/main/actions/syncdatetime', 1)  # Sync date and time to computer
        result = self.set('/main/actions/uilock', 1)        # Don't let the UI change

        # Get Camera Properties
        self.get_serial_number()


    # -------------------------------------------------------------------------
    # Generic Panoptes Camera Methods
    # -------------------------------------------------------------------------
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

    def is_exposing(self):
        '''
        '''
        pass

    # -------------------------------------------------------------------------
    # Actions Specific to Canon / gphoto
    # -------------------------------------------------------------------------

    def get_serial_number(self):
        ''' Gets the 'EOS Serial Number' property

        Populates the self.serial_number property

        Returns:
            str:    The serial number
        '''
        self.serial_number = self.get('Serial Number')
        return self.serial_number

    def get_iso(self):
        '''
        Queries the camera for the ISO setting and populates the self.iso
        property with a string containing the ISO speed.
        '''
        self.iso = self.get('ISO Speed')
        return self.iso

    def set_iso(self, iso):
        '''
        Sets the ISO speed of the camera after checking that the input value (a
        string or in) is in the list of allowed values in the self.iso_options
        dictionary.
        '''
        if not iso:
            iso = 400
        print(iso)
        self.get_iso()
        self.set('ISO Speed', iso)

    def get_model(self):
        '''
        Gets the Camera Model string from the camera and populates the
        self.model property.
        '''
        self.model = self.get('Camera Model')
        return self.model

    def get_shutter_count(self):
        '''
        Gets the shutter count value and populates the self.shutter_count
        property.
        '''
        self.shutter_count = self.get('Shutter Counter')
        return self.shutter_count

    def construct_filename(self):
        '''
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        '''
        if self.last_start_time:
            filename = self.last_start_time.strftime('image_%Y%m%dat%H%M%S.cr2')
        else:
            filename = self.last_start_time.strftime('image.cr2')
        return filename

    def take_exposure(self, exptime):
        '''
        gphoto2 --wait-event=2s --set-config eosremoterelease=2 --wait-event=10s --set-config eosremoterelease=4 --wait-event-and-download=5s

        Tested With:
            * Canon EOS 100D
        '''
        self.logger.info('Taking {} second exposure'.format(exptime))
        self.last_start_time = datetime.datetime.now()
        filename = construct_filename(self)
        cmd = ['--wait-event=2s',
               '--set-config', 'eosremoterelease=4',
               '--wait-event={:d}s'.format(int(exptime)),
               '--set-config', 'eosremoterelease=0',
               '--wait-event-and-download=0s',
               '--filename="{:s}"'.format(filename),
               '--force-overwrite',
               ]
        result = self.command(cmd)

        savedfile = None
        for line in result:
            IsSavedFile = re.match('Saving file as (.+\.[cC][rR]2)', line)
            if IsSavedFile:
                savedfile = IsSavedFile.group(1)
        end_time = datetime.datetime.now()
        elapsed = (end_time - self.last_start_time).total_seconds()
        self.logger.debug('  Elapsed time = {:.1f} s'.format(elapsed))
        self.logger.debug('  Overhead time = {:.1f} s'.format(elapsed - exptime))
        if savedfile:
            if os.path.exists(savedfile):
                return savedfile
            else:
                return None
        else:
            return None


    def simple_capture_and_download(self, exptime):
        '''
        '''
        self.logger.info('Starting capture')
        exptime_index = 23
        result = self.set('/main/capturesettings/shutterspeed', exptime_index)
        result = self.command('--capture-image-and-download')

        # Below is for using open bulb exposure

        # result = self.command('--wait-event=2s')
        # result = self.set('/main/actions/eosremoterelease', '2') # Open shutter
        # result = self.command('--wait-event={}s'.format(exposure_seconds))
        # result = self.set('/main/actions/eosremoterelease', '4') # Close shutter
        # result = self.command('--wait-event-and-download=5s')
        self.logger.info('Done with capture')


# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------
