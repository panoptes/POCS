import os
import sys
import re
import time
import datetime
import subprocess

import panoptes.utils.logger as logger
import panoptes.utils.config as config

@logger.has_logger
@config.has_config
class AbstractCamera(object):
    """
    Abstract Camera class
    """

    def __init__(self, config=dict(), USB_port='usb:001,017', connect_on_startup=False):
        """
        Initialize the camera
        """
        # Create an object for just the mount config items
        self.camera_config = config if len(config) else dict()

        # Get the model and port number
        model = self.camera_config.get('model')
        port = self.camera_config.get('port')

        # Check the config for required items
        assert self.camera_config.get('port') is not None, self.logger.error('No mount port specified, cannot create mount\n {}'.format(self.camera_config))

        self.logger.info('Creating camera: {} {}'.format(model, port))

        self.cooled = True
        self.cooling = False
        self.model = model
        self.USB_port = port
        self.name = None
        self.properties = None

        # Load the properties
        if connect_on_startup: self.connect()


    def load_properties(self):
        '''
        '''
        self.logger.debug('Get All Properties')
        command = ['gphoto2', '--port', self.USB_port, '--list-config']
        result = subprocess.check_output(command)
        self.properties = result.decode('utf-8').split('\n')
        if self.properties:
            self.logger.debug('  Found {} properties'.format(len(self.properties)))
        else:
            self.logger.warning('  Could not determine properties.')

    def get(self, property):
        '''
        '''
        assert self.properties
        if not property in self.properties:
            self.logger.warning('  {} is not in list of properties for this camera'.format(property))
            return False
        else:
            self.logger.info('Getting {} from camera'.format(property))
            command = ['gphoto2', '--port', self.USB_port, '--get-config', property]
            result = subprocess.check_output(command, stderr=subprocess.STDOUT)
            lines = result.decode('utf-8').split('\n')
            return lines


    def set(self, property, value):
        '''
        '''
        assert self.properties
        if not property in self.properties:
            self.logger.warning('  {} is not in list of properties for this camera'.format(property))
            return False
        else:
            self.logger.info('Setting {} on camera'.format(property))
            command = ['gphoto2', '--port', self.USB_port, '--set-config', '{}={}'.format(property, value)]
            result = subprocess.check_output(command)
            lines = result.decode('utf-8').split('\n')
            return lines


    def command(self, command):
        '''
        '''
        self.logger.info('Sending command {} to camera'.format(command))
        command = ['gphoto2', '--port', self.USB_port,  '--filename=IMG_%y%m%d_%H%M%S.cr2', command]
        result = subprocess.check_output(command)
        lines = result.decode('utf-8').split('\n')
        return lines


    def get_iso(self):
        '''
        Queries the camera for the ISO setting and populates the self.iso
        property with a string containing the ISO speed.

        Also examines the output of the command to populate the self.iso_options
        property which is a dictionary associating the iso speed (as a string)
        with the numeric value used as input for the set_iso() method.  The keys
        in this dictionary are the allowed values of the ISO for this camera.
        '''
        lines = self.get('/main/imgsettings/iso')
        if re.match('Label: ISO Speed', lines[0]) and re.match('Type: RADIO', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.iso = MatchObj.group(1)
                self.logger.debug('  ISO = {}'.format(self.iso))
        ## Get Choices
        self.iso_options = {}
        for line in lines:
            MatchOption = re.match('Choice: (\d{1,2}) (\d{3,})', line)
            if MatchOption:
                self.iso_options[MatchOption.group(2)] = int(MatchOption.group(1))
        return self.iso

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
            lines = self.set('/main/imgsettings/iso', '{}'.format(self.iso_options[str(iso)]))
            print(lines)


    def get_serial_number(self):
        '''
        Gets the generic Serial Number property and populates the
        self.serial_number property.

        Note: Some cameras override this. See `canon.get_serial_number`
        '''
        lines = self.get('/main/status/serialnumber')
        if re.match('Label: Serial Number', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.serial_number = MatchObj.group(1)
                self.logger.debug('  Serial Number: {}'.format(self.serial_number))
        return self.serial_number


    def get_model(self):
        '''
        Gets the Camera Model string from the camera and populates the
        self.model property.
        '''
        lines = self.get('/main/status/cameramodel')
        if re.match('Label: Camera Model', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.model = MatchObj.group(1)
                self.logger.debug('  Camera Model: {}'.format(self.model))
        return self.model


    def get_device_version(self):
        '''
        Gets the Device Version string from the camera and populates the
        self.device_version property.
        '''
        lines = self.get('/main/status/deviceversion')
        if re.match('Label: Device Version', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.device_version = MatchObj.group(1)
                self.logger.debug('  Device Version: {}'.format(self.device_version))
        return self.device_version


    def get_shutter_count(self):
        '''
        Gets the shutter count value and populates the self.shutter_count
        property.
        '''
        lines = self.get('/main/status/shuttercounter')
        if re.match('Label: Shutter Counter', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.shutter_count = int(MatchObj.group(1))
                self.logger.debug('  Shutter Count = {}'.format(self.shutter_count))
        return self.shutter_count


    ##-------------------------------------------------------------------------
    ## Actions Specific to Canon / gphoto
    ##-------------------------------------------------------------------------
    def simple_capture_and_download(self, exptime):
        '''
        '''
        self.logger.info('Starting capture')
        exptime_index = 23
        result = self.set('/main/capturesettings/shutterspeed', exptime_index)
        result = self.command('--capture-image-and-download')

        ## Below is for using open bulb exposure
            
        # result = self.command('--wait-event=2s')
        # result = self.set('/main/actions/eosremoterelease', '2') # Open shutter
        # result = self.command('--wait-event={}s'.format(exposure_seconds))
        # result = self.set('/main/actions/eosremoterelease', '4') # Close shutter
        # result = self.command('--wait-event-and-download=5s')
        self.logger.info('Done with capture')



    ##-------------------------------------------------------------------------
    ## Generic Panoptes Camera Methods
    ##-------------------------------------------------------------------------
    def connect(self):
        '''
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        '''
        self.logger.info('Connecting to camera')
        self.load_properties()
        ## Set auto power off to infinite
        result = self.set('/main/settings/autopoweroff', 0)
        # print(result)
        ## Set capture format to RAW
        result = self.set('/main/imgsettings/imageformat', 9)
        # print(result)
        ## Sync date and time to computer
        result = self.set('/main/actions/syncdatetime', 1)
        # print(result)
        ## Set review time to zero (keeps screen off)
        result = self.set('/main/settings/reviewtime', 0)
        # print(result)
        ## Set copyright string
        result = self.set('/main/settings/copyright', 'ProjectPANOPTES')
        # print(result)
        ## Get Camera Properties
        self.get_serial_number()


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


def list_connected_cameras(logger=None):
    """
    Uses gphoto2 to try and detect which cameras are connected.

    Cameras should be known and placed in config but this is a useful utility.
    """

    command = ['gphoto2', '--auto-detect']
    result = subprocess.check_output(command)
    lines = result.decode('utf-8').split('\n')

    ports = []

    for line in lines:
        camera_match = re.match('([\w\d\s_\.]{30})\s(usb:\d{3},\d{3})', line)
        if camera_match:
            camera_name = camera_match.group(1).strip()
            port = camera_match.group(2).strip()
            if logger: logger.info('Found "{}" on port "{}"'.format(camera_name, port))
            ports.append(port)

    return ports


if __name__ == '__main__':
    CameraPorts = list_connected_cameras()
    Cameras = []
    for port in CameraPorts:
        Cameras.append(Camera(USB_port=port))

    for camera in Cameras:
        camera.load_properties()
        camera.simple_capture_and_download(1/10)
        sys.exit(0)
