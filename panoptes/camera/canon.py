#!/usr/bin/env python

# Note Mac users may need to kill a process to claim camera with gphoto:
# killall PTPCamera

from panoptes.camera import AbstractCamera
import panoptes.utils.logger as logger

import re
import yaml
import subprocess
import os
import datetime

import panoptes.utils.logger as logger
import panoptes.utils.config as config


@logger.has_logger
@config.has_config
class Camera(AbstractCamera):

    def __init__(self, config=dict(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gphoto = 'gphoto2'

        # Get the model and port number
        self.model = self.camera_config.get('model')
        self.port = self.camera_config.get('port')

        print(config)

        # Check the config for required items
        assert self.camera_config.get('port') is not None, self.logger.error('No camera port specified\n {}'.format(self.camera_config))

        self.logger.info('Creating camera: {} {}'.format(self.model, self.port))

        self.cooled = True
        self.cooling = False
        self.last_start_time = None


    ##-------------------------------------------------------------------------
    ## Generic Panoptes Camera Methods
    ##-------------------------------------------------------------------------
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
        result = subprocess.check_output(command).decode('utf-8').split('\n')
        self.properties = parse_config(result)
        return self.properties


    def get(self, property_name):
        '''
        '''
        assert self.properties
        if not property_name in self.properties.keys():
            self.logger.warning('  {} is not in list of properties for this camera'.format(property_name))
            return False
        else:
            self.logger.info('Getting {} from camera'.format(property_name))
            command = [self.gphoto, '--port', self.port, '--get-config', self.properties[property_name]['ID']]
            result = subprocess.check_output(command, stderr=subprocess.STDOUT)
            lines = result.decode('utf-8').split('\n')
            output = parse_config(lines)
            return output['Current']



    def set(self, property_name, value):
        '''
        '''
        assert self.properties
        if not property_name in self.properties.keys():
            self.logger.warning('  {} is not in list of properties for this camera'.format(property_name))
            return False
        else:
            ## If the input value is an int
            if isinstance(value, int):
                choiceint = value
            if not isinstance(value, int):
                try:
                    choiceint = int(value)
                except:
                    if 'Choices' in self.properties[property_name].keys():
                        choices = self.properties[property_name]['Choices']
                        if not value in choices.keys():
                            self.logger.warning('  {} is not in list of choices for this proprty'.format(value))
                            self.logger.debug('Valid Choices Are:')
                            for key in choices.keys():
                                self.logger.debug('  {}'.format(key))
                            choiceint = None
                        else:
                            choiceint = choices[value]
                    else:
                        choiceint = None

            if choiceint:
                self.logger.info('Setting {} to {} ({})'.format(property_name, value, choiceint))
                command = [self.gphoto, '--port', self.port, '--set-config', '{}={}'.format(self.properties[property_name]['ID'], choiceint)]
                result = subprocess.check_output(command)
                lines = result.decode('utf-8').split('\n')
                return lines


    def get_serial_number(self):
        '''
        Gets the 'EOS Serial Number' property and populates the
        self.serial_number property
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
        if not iso: iso = 400
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
            * Canon EOS 6D
        '''
        self.logger.info('Taking {} second exposure'.format(exptime))
        self.last_start_time = datetime.datetime.now()
        filename = construct_filename(self)
        cmd = ['gphoto2', '--wait-event=2s',\
               '--set-config', 'eosremoterelease=2',\
               '--wait-event={:d}s'.format(int(exptime)),\
               '--set-config', 'eosremoterelease=4',\
               '--wait-event-and-download=5s',\
               '--filename="{:s}"'.format(filename),\
               '--force-overwrite',\
               ]
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        lines = result.decode('utf-8').split('\n')
        ## Look for "Saving file as"
        savedfile = None
        for line in lines:
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


##-----------------------------------------------------------------------------
## Functions
##-----------------------------------------------------------------------------
def parse_config(lines):
    config_dict = {}
    yaml_string = ''
    for line in lines:
        IsID = len(line.split('/')) > 1
        IsLabel = re.match('^Label:\s(.*)', line)
        IsType  = re.match('^Type:\s(.*)', line)
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
        elif line == '': pass
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
            if logger: logger.info('Found "{}" on port "{}"'.format(camera_name, port))
            ports.append(port)

    return ports


##-----------------------------------------------------------------------------
## 
##-----------------------------------------------------------------------------
if __name__ == '__main__':
    import panoptes
    pan = panoptes.Panoptes()
    cam = pan.observatory.cameras[0]
    result = cam.take_exposure(5)
    print(result)

#     cam.list_properties()
#     for item in cam.properties.keys():
#         print('{}: {}'.format(item, cam.properties[item]['Current']))
# 
#     print()
# 
#     property = 'Focus Mode'
#     value = 'One Shot'
# #     value = 'AI Focus'
#     result = cam.get(property)
#     print('Current {} = {}'.format(property, result))
#     print('Setting {} to {}'.format(property, value))
#     cam.set(property, value)
#     result = cam.get(property)
#     print('Current {} = {}'.format(property, result))
# 
#     print()
# 
#     cam.get_shutter_count()
#     print(cam.shutter_count)
# 
#     print()
# 
#     cam.get_iso()
#     print(cam.iso)
#     cam.set_iso('100')
#     print(cam.iso)
    
