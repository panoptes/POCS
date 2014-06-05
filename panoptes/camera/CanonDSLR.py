import datetime
import os
import sys
import re
import time
import subprocess

from panoptes.utils import logger
from panoptes.camera import camera


def list_connected_cameras(logger=None):
    if logger: logger.debug('  Get Serial Number')
    command = ['sudo', 'gphoto2', '--auto-detect']
    result = subprocess.check_output(command)
    lines = result.decode('utf-8').split('\n')
    nCameras = len(lines) - 2
    PortsDict = {}
    for line in lines[2:]:
        MatchCamera = re.match('([\w\d\s_\.]{30})\s(usb:\d{3},\d{3})', line)
        if MatchCamera:
            cameraname = MatchCamera.group(1).strip()
            port = MatchCamera.group(2).strip()
            if logger: logger.info('Found "{}" on port "{}"'.format(cameraname, port))
            PortsDict[port] = cameraname
    return PortsDict


@logger.has_logger
@logger.set_log_level(level='debug')
class CanonDSLR(camera.Camera):
    def __init__(self, USB_port='usb:001,017'):
        super().__init__()
        self.logger.info('Setting up Canon DSLR camera')
        self.cooled = True
        self.cooling = False
        self.model = None
        self.USB_port = USB_port
        self.name = None
        ## Connect to Camera
        self.connect()
        self.logger.debug('Configuring camera settings')
        ## Set auto power off to infinite
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


    ##-------------------------------------------------------------------------
    ## Settings
    ##-------------------------------------------------------------------------
    def get_iso(self):
        '''
        Queries the camera for the ISO setting and populates the self.iso
        property with a string containing the ISO speed.
        
        Also examines the output of the command to populate the self.iso_options
        property which is a dictionary associating the iso speed (as a string)
        with the numeric value used as input for the set_iso() method.  The keys
        in this dictionary are the allowed values of the ISO for this camera.
        '''
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
        '''
        Sets the ISO speed of the camera after checking that the input value (a
        string or in) is in the list of allowed values in the self.iso_options
        dictionary.
        '''
        self.get_iso()
        if not str(iso) in self.iso_options.keys():
            self.logger.warning('  ISO {} not in options for this camera.'.format(iso))
        else:
            self.logger.debug('  Setting ISO to {}'.format(iso))
            command = ['sudo', 'gphoto2', '--port', self.USB_port, '--set-config', '/main/imgsettings/iso={}'.format(self.iso_options[str(iso)])]
            result = subprocess.check_output(command)


    def get_serial_number(self):
        '''
        Gets the 'EOS Serial Number' property and populates the 
        self.serial_number property
        '''
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
        '''
        Gets the Camera Model string from the camera and populates the
        self.model property.
        '''
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
        '''
        Gets the Device Version string from the camera and populates the
        self.device_version property.
        '''
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
        '''
        Gets the shutter count value and populates the self.shutter_count
        property.
        '''
        self.logger.debug('  Get shutter count')
        command = ['sudo', 'gphoto2', '--port', self.USB_port, '--get-config=/main/status/shuttercounter']
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        if re.match('Label: Shutter Counter', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.shutter_count = int(MatchObj.group(1))
                self.logger.debug('  Shutter Count = {}'.format(self.shutter_count))


    ##-------------------------------------------------------------------------
    ## Actions
    ##-------------------------------------------------------------------------
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


    def take_image(self, exptime=20, nframes=1, interval=1):
        '''
        '''
        assert int(exptime)
        assert int(nframes)
        assert int(interval)
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


    ##-------------------------------------------------------------------------
    ## Query Status Methods
    ##-------------------------------------------------------------------------
    def is_exposing(self):
        '''
        '''
        pass



if __name__ == '__main__':
    result = list_connected_cameras()

#     camera = CanonDSLR(USB_port='usb:001,017')
#     camera.get_iso()
#     print(camera.iso_options)
#     camera.set_iso(iso=400)
#     camera.get_iso()
