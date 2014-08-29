#!/usr/bin/env python

from panoptes.camera import AbstractCamera
import panoptes.utils.logger as logger

import re
import yaml
import subprocess


@logger.set_log_level(level='debug')
@logger.has_logger
class Camera(AbstractCamera):

    def __init__(self, port=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gphoto = 'gphoto2'
        self.properties = None
        self.port = port


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


    ##-------------------------------------------------------------------------
    ## Actions Specific to Canon / gphoto
    ##-------------------------------------------------------------------------
    def list_properties(self):
        command = [self.gphoto]
        if self.port:
            command.append('--port')
            command.append(self.port)
        command.append('--list-all-config')
        result = subprocess.check_output(command).split('\n')
        yaml_string = ''
        for line in result:
            IsLabel = re.match('^Label:\s(.*)', line)
            IsType  = re.match('^Type:\s(.*)', line)
            IsCurrent = re.match('^Current:\s(.*)', line)
            IsChoice = re.match('^Choice:\s(.*)', line)
            IsPrintable = re.match('^Printable:\s(.*)', line)
            if IsLabel: line = '  {}'.format(line)
            elif IsType: line = '  {}'.format(line)
            elif IsCurrent: line = '  {}'.format(line)
            elif IsChoice: line = '  {}'.format(line)
            elif IsPrintable: line = '  {}'.format(line)
            elif line == '': pass
            else: line = '- id: {}'.format(line)
            yaml_string += '{}\n'.format(line)
        properties_list = yaml.load(yaml_string)
        properties = {}
        for property in properties_list:
            if property['Label']:
                properties[property['Label']] = property
        self.properties = properties
        return properties


    def get(self, property_name):
        '''
        '''
        assert self.properties
        if not property_name in self.properties.keys():
            self.logger.warning('  {} is not in list of properties for this camera'.format(property_name))
            return False
        else:
            self.logger.info('Getting {} from camera'.format(property_name))
            command = [self.gphoto, '--port', self.port, '--get-config', self.properties[property_name]['id']]
            result = subprocess.check_output(command, stderr=subprocess.STDOUT)
            lines = result.decode('utf-8').split('\n')
            return lines


    def set(self, property_name, value):
        '''
        '''
        assert self.properties
        if not property_name in self.properties.keys():
            self.logger.warning('  {} is not in list of properties for this camera'.format(property_name))
            return False
        else:
            self.logger.info('Setting {} on camera'.format(property_name))
            command = [self.gphoto, '--port', self.port, '--set-config', '{}={}'.format(self.properties[property_name]['id'], value)]
            result = subprocess.check_output(command)
            lines = result.decode('utf-8').split('\n')
            return lines


#     def get_serial_number(self):
#         '''
#         Gets the 'EOS Serial Number' property and populates the
#         self.serial_number property
#         '''
#         lines = self.get('/main/status/eosserialnumber')
#         if re.match('Label: Serial Number', lines[0]) and re.match('Type: TEXT', lines[1]):
#             MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
#             if MatchObj:
#                 self.serial_number = MatchObj.group(1)
#                 self.logger.debug('  Serial Number: {}'.format(self.serial_number))
#         return self.serial_number
# 
# 
#     def get_iso(self):
#         '''
#         Queries the camera for the ISO setting and populates the self.iso
#         property with a string containing the ISO speed.
# 
#         Also examines the output of the command to populate the self.iso_options
#         property which is a dictionary associating the iso speed (as a string)
#         with the numeric value used as input for the set_iso() method.  The keys
#         in this dictionary are the allowed values of the ISO for this camera.
#         '''
#         lines = self.get('/main/imgsettings/iso')
#         if re.match('Label: ISO Speed', lines[0]) and re.match('Type: RADIO', lines[1]):
#             MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
#             if MatchObj:
#                 self.iso = MatchObj.group(1)
#                 self.logger.debug('  ISO = {}'.format(self.iso))
#         ## Get Choices
#         self.iso_options = {}
#         for line in lines:
#             MatchOption = re.match('Choice: (\d{1,2}) (\d{3,})', line)
#             if MatchOption:
#                 self.iso_options[MatchOption.group(2)] = int(MatchOption.group(1))
#         return self.iso
# 
# 
#     def set_iso(self, iso=200):
#         '''
#         Sets the ISO speed of the camera after checking that the input value (a
#         string or in) is in the list of allowed values in the self.iso_options
#         dictionary.
#         '''
#         self.get_iso()
#         if not str(iso) in self.iso_options.keys():
#             self.logger.warning('  ISO {} not in options for this camera.'.format(iso))
#         else:
#             self.logger.debug('  Setting ISO to {}'.format(iso))
#             lines = self.set('/main/imgsettings/iso', '{}'.format(self.iso_options[str(iso)]))
#             print(lines)
# 
# 
#     def get_serial_number(self):
#         '''
#         Gets the generic Serial Number property and populates the
#         self.serial_number property.
# 
#         Note: Some cameras override this. See `canon.get_serial_number`
#         '''
#         lines = self.get('/main/status/serialnumber')
#         if re.match('Label: Serial Number', lines[0]) and re.match('Type: TEXT', lines[1]):
#             MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
#             if MatchObj:
#                 self.serial_number = MatchObj.group(1)
#                 self.logger.debug('  Serial Number: {}'.format(self.serial_number))
#         return self.serial_number
# 
# 
#     def get_model(self):
#         '''
#         Gets the Camera Model string from the camera and populates the
#         self.model property.
#         '''
#         lines = self.get('/main/status/cameramodel')
#         if re.match('Label: Camera Model', lines[0]) and re.match('Type: TEXT', lines[1]):
#             MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
#             if MatchObj:
#                 self.model = MatchObj.group(1)
#                 self.logger.debug('  Camera Model: {}'.format(self.model))
#         return self.model
# 
# 
#     def get_device_version(self):
#         '''
#         Gets the Device Version string from the camera and populates the
#         self.device_version property.
#         '''
#         lines = self.get('/main/status/deviceversion')
#         if re.match('Label: Device Version', lines[0]) and re.match('Type: TEXT', lines[1]):
#             MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
#             if MatchObj:
#                 self.device_version = MatchObj.group(1)
#                 self.logger.debug('  Device Version: {}'.format(self.device_version))
#         return self.device_version
# 
# 
#     def get_shutter_count(self):
#         '''
#         Gets the shutter count value and populates the self.shutter_count
#         property.
#         '''
#         lines = self.get('/main/status/shuttercounter')
#         if re.match('Label: Shutter Counter', lines[0]) and re.match('Type: TEXT', lines[1]):
#             MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
#             if MatchObj:
#                 self.shutter_count = int(MatchObj.group(1))
#                 self.logger.debug('  Shutter Count = {}'.format(self.shutter_count))
#         return self.shutter_count
# 
# 
#     def simple_capture_and_download(self, exptime):
#         '''
#         '''
#         exptime_index = 23
#         result = self.set('/main/capturesettings/shutterspeed', exptime_index)
#         # print(result)
#         result = self.command('--capture-image-and-download')
#         # print(result)





##-----------------------------------------------------------------------------
## Functions
##-----------------------------------------------------------------------------
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
