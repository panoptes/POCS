import datetime
import os
import sys
import re
import time
import subprocess

from panoptes.utils import logger
from panoptes.camera import camera


@logger.has_logger
@logger.set_log_level(level='debug')
class CanonDSLR(camera.Camera):
    def __init__(self, USB_port='usb:001,017'):
        super().__init__()
        self.logger.info('Setting up Canon DSLR camera')
        self.cooled = True
        self.model = None
        self.USB_port = USB_port
        self.name = None
        ## Connect to Camera
        self.connect()
        self.logger.debug('Configuring camera settings')
        ## Set auto power off to 0
        self.logger.debug('  Setting auto power off time to infinite')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', '/main/settings/autopoweroff=0']
        result = subprocess.check_output(command)
        ## Set capture format to RAW
        self.logger.debug('  Setting format to RAW')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', '/main/imgsettings/imageformat=9']
        result = subprocess.check_output(command)
        ## Set shutterspeed to bulb
        self.logger.debug('  Setting shutter speed to bulb')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', 'shutterspeed=bulb']
        result = subprocess.check_output(command)
        ## Sync date and time to computer
        self.logger.debug('  Syncing date and time to computer')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', '/main/actions/syncdatetime=1']
        result = subprocess.check_output(command)
        ## Set review time to zero (keeps screen off)
        self.logger.debug('  Set review time to zero (keeps screen off)')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', '/main/settings/reviewtime=0']
        result = subprocess.check_output(command)
        ## Set copyright string
        self.logger.debug('  Set copyright string to Project_PANOPTES')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', '/main/settings/copyright=Project_PANOPTES']
        result = subprocess.check_output(command)
        ## Get Camera Properties
        self.get_serial_number()


    def get_iso(self):
        self.logger.debug('  Get ISO value')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--get-config=/main/imgsettings/iso']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        if re.match('Label: ISO Speed', lines[0]) and re.match('Type: RADIO', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.iso = MatchObj.group(1)
                self.logger.debug('  ISO = {}'.format(self.iso))
        ## Get Choices
        self.iso_options = {}
        for line in lines[3:]:
            MatchOption = re.match('Choice: (\d{1,2}) (\d{3,})', line)
            if MatchOption:
                self.iso_options[MatchOption.group(2)] = int(MatchOption.group(1))


    def set_iso(self, iso=200):
        self.get_iso()
        if not str(iso) in self.iso_options.keys():
            self.logger.warning('  ISO {} not in options for this camera.'.format(iso))
        else:
            self.logger.debug('  Setting ISO to {}'.format(iso))
            command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', '/main/imgsettings/iso={}'.format(self.iso_options[str(iso)])]
            result = subprocess.check_output(command)


    def get_serial_number(self):
        self.logger.debug('  Get Serial Number')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--get-config=/main/status/eosserialnumber']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        if re.match('Label: Serial Number', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.serial_number = MatchObj.group(1)
                self.logger.debug('  Serial Number: {}'.format(self.serial_number))


    def get_model(self):
        self.logger.debug('  Get model')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--get-config=/main/status/cameramodel']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        if re.match('Label: Camera Model', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.model = MatchObj.group(1)
                self.logger.debug('  Camera Model: {}'.format(self.model))


    def get_device_version(self):
        self.logger.debug('  Get device version')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--get-config=/main/status/deviceversion']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        if re.match('Label: Device Version', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.device_version = MatchObj.group(1)
                self.logger.debug('  Device Version: {}'.format(self.device_version))


    def get_shutter_count(self):
        self.logger.debug('  Get shutter count')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--get-config=/main/status/shuttercounter']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        if re.match('Label: Shutter Counter', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.shutter_count = int(MatchObj.group(1))
                self.logger.debug('  Shutter Count = {}'.format(self.shutter_count))


    def connect(self):
        '''
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        '''
        self.model = None
        self.logger.info('Connecting to camera')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--summary']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        for line in lines:
            MatchModel = re.match('Model:\s([\w\d\s\.\-]+)', line)
            if MatchModel:
                self.model = MatchModel.group(1)
        if self.model:
            self.logger.debug('Camera model: {}'.format(self.model))
            self.connected = True
        if self.connected:
            self.logger.info('Connected to {}'.format(self.model))
        else:
            self.logger.warning('Failed to connect')


    def take_image(self, exptime=120, nframes=1, interval=1):
        '''
        '''
        assert int(exptime)
        assert int(nframes)
        self.logger.info('Commanding bulb exposure on camera.  exptime={} s'.format(exptime))
        self.logger.debug('  Setting exposure time on camera')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--bulb={}'.format(exptime)]
        result = subprocess.check_output(command)
        self.logger.debug('  Setting number of frames to capture to {}'.format(nframes))
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--frames={}'.format(nframes)]
        result = subprocess.check_output(command)
        self.logger.debug('  Setting interval between frames to {} s'.format(interval))
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--interval={}'.format(interval)]
        result = subprocess.check_output(command)
        self.logger.debug('  Triggering exposure.')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--trigger-capture', '--keep']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        for line in lines:
            print(line)

    def start_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.info('No camera cooling available')


    def stop_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.info('No camera cooling available')


    ##-------------------------------------------------------------------------
    ## Query/Update Methods
    ##-------------------------------------------------------------------------
    def is_cooling(self):
        '''
        '''
        pass


    def is_cooled(self):
        '''
        '''
        pass


    def is_exposing(self):
        '''
        '''
        pass



if __name__ == '__main__':
    camera = CanonDSLR(USB_port='usb:001,017')
    camera.get_iso()
    print(camera.iso_options)
    camera.set_iso(iso=400)
    camera.get_iso()
