import os
import sys
import re
import time
import datetime
import subprocess
import yaml

from ..utils.logger import has_logger
from ..utils.config import load_config
from ..utils import listify

@has_logger
class AbstractCamera(object):
    """
    Abstract Camera class
    """
    pass

    def __init__(self, config=dict()):
        """
        Initialize the camera
        """
        self.config = load_config()
        # Create an object for just the mount config items
        self.camera_config = config if len(config) else dict()

        # Get the model and port number
        model = self.camera_config.get('model')
        port = self.camera_config.get('port')

        # Check the config for required items
        assert self.camera_config.get('port') is not None, self.logger.error(
            'No camera port specified, cannot create camera\n {}'.format(self.camera_config))

        self.logger.info('Creating camera: {} {}'.format(model, port))

        self.gphoto = self.config.get('gphoto2', '/usr/local/bin/gphoto2')

        self.cooled = True
        self.cooling = False
        self.model = model
        self.USB_port = port
        self.name = None
        self.properties = None

##################################################################################################
# Methods
##################################################################################################

    def command(self, command):
        ''' Runs a command on the camera using gphoto2

        This should be the only user-accessible way to run commands on the camera.

        Args:
            command(list):   Commands to be passed to the camera

        Returns:
            list:           UTF-8 decoded response from camera
        '''

        # Generic command
        cam_command = ['gphoto2', '--port', self.USB_port]

        # Add in the user command
        cam_command.extend(listify(command))

        lines = []

        self.logger.debug('Sending command {} to camera'.format(cam_command))
        # Run the actual command
        try:
            result = subprocess.check_output(cam_command, stderr=subprocess.STDOUT)
            lines = result.decode('utf-8').split('\n')
        except subprocess.CalledProcessError as err:
            self.logger.warning("Problem running command on camera {}: {} \n {}".format(self.name, command, err))

        self.logger.debug('Response from camera: {}'.format(lines))
        return lines


    def load_properties(self):
        ''' Load properties from the camera

        Reads all the configuration properties available via gphoto2 and populates
        a local list with these entries.
        '''
        self.logger.debug('Get All Properties')
        command = ['--list-all-config']

        self.properties = parse_config(self.command(command))

        if self.properties:
            self.logger.debug('  Found {} properties'.format(len(self.properties)))
        else:
            self.logger.warning('  Could not determine properties.')


    def get(self, property):
        ''' Get a value for the given property

        Args:
            property(str):      Property name

        Returns:
            list:               A list containing string responses from camera
        '''
        assert self.properties, self.logger.warning("No properties available for {}".format(self.name))

        lines = []

        if property not in self.properties:
            self.logger.warning(
                '{} is not in list of properties for this camera'.format(property))
        else:
            self.logger.debug('Getting {} from camera'.format(property))

            lines = self.command(['--get-config', property])

        return lines

    def set(self, property, value):
        ''' Sets a property for the camera

        Args:
            property(str):  The property to set
            value(str):     The value to set for the property

        Returns:
            list:           Response from camera as list of lines
        '''
        assert self.properties

        lines = []

        if not property in self.properties:
            self.logger.warning(
                '  {} is not in list of properties for this camera'.format(property))
        else:
            self.logger.info('Setting {} on camera'.format(property))
            lines = self.command(['--set-config', '{}={}'.format(property, value)])

        return lines

    def get_iso(self):
        '''
        Queries the camera for the ISO setting and populates the self.iso
        property with a string containing the ISO speed.

        Also examines the output of the command to populate the self.iso_options
        property which is a dictionary associating the iso speed (as a string)
        with the numeric value used as input for the set_iso() method.  The keys
        in this dictionary are the allowed values of the ISO for this camera.

        Returns:
            str:        The current ISO setting
        '''
        lines = self.get('/main/imgsettings/iso')

        if re.match('Label: ISO Speed', lines[0]) and re.match('Type: RADIO', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.iso = MatchObj.group(1)
                self.logger.debug('  ISO = {}'.format(self.iso))
        # Get Choices
        self.iso_options = {}
        for line in lines:
            MatchOption = re.match('Choice: (\d{1,2}) (\d{3,})', line)
            if MatchOption:
                self.iso_options[MatchOption.group(2)] = int(MatchOption.group(1))

        return self.iso

    def set_iso(self, iso=100):
        ''' Sets the ISO speed of the camera.

        Checks that the input value (a string or int) is in the list of allowed values in
        the self.iso_options dictionary.
        '''
        self.get_iso()
        if str(iso) not in self.iso_options:
            self.logger.warning('ISO {} not in options for this camera.'.format(iso))
        else:
            self.logger.debug('Setting ISO to {}'.format(iso))
            lines = self.set('/main/imgsettings/iso', '{}'.format(self.iso_options[str(iso)]))

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


    # -------------------------------------------------------------------------
    # Generic Panoptes Camera Methods
    # -------------------------------------------------------------------------
    def start_cooling(self):
        '''
        This does nothing for a Canon DSLR as it does not have cooling.
        '''
        self.logger.info('No camera cooling available')
        self.cooled = None
        self.cooling = None

        # Create an object for just the camera config items
        self.camera_config = config if len(config) else dict()

        self.filename_pattern = self.camera_config.get('filename_pattern')

    def construct_filename(self):
        '''
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        '''
        pass

##################################################################################################
# NotImplemented Methods
##################################################################################################

    def connect(self):
        ''' Connection method for the camera. '''
        raise NotImplementedError

##################################################################################################
# Class Methods
##################################################################################################

def parse_config(lines):
    config_dict = {}
    yaml_string = ''
    for line in lines:
        IsID = len(line.split('/')) > 1
        IsLabel = re.match('^Label:\s(.*)', line)
        IsType = re.match('^Type:\s(.*)', line)
        IsCurrent = re.match('^Current:\s(.*)', line)
        IsChoice = re.match('^Choice:\s(\d+)\s(.*)', line)
        IsPrintable = re.match('^Printable:\s(.*)', line)
        if IsLabel:
            line = '  {}'.format(line)
        elif IsType:
            line = '  {}'.format(line)
        elif IsCurrent:
            line = '  {}'.format(line)
        elif IsChoice:
            if int(IsChoice.group(1)) == 0:
                line = '  Choices:\n    {}: {:d}'.format(IsChoice.group(2), int(IsChoice.group(1)))
            else:
                line = '    {}: {:d}'.format(IsChoice.group(2), int(IsChoice.group(1)))
        elif IsPrintable:
            line = '  {}'.format(line)
        elif IsID:
            line = '- ID: {}'.format(line)
        elif line == '':
            pass
        else:
            print('Line Not Parsed: {}'.format(line))
        yaml_string += '{}\n'.format(line)
    properties_list = yaml.load(yaml_string)
    if isinstance(properties_list, list):
        properties = {}
        for property in properties_list:
            if property['Label']:
                properties[property['Label']] = property
    else:
        properties = properties_list
    return properties


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
            if logger:
                logger.info('Found "{}" on port "{}"'.format(camera_name, port))
            ports.append(port)

    return ports
