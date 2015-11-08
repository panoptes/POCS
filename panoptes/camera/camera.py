from ..utils.indi import PanIndiDevice

from ..utils.logger import has_logger
from ..utils import error
from ..utils import listify

import os
import re
import shutil
import subprocess
import yaml


@has_logger
class AbstractCamera(object):

    """ Base class for both INDI and gphoto2 cameras """

    def __init__(self, config):
        self.config = config

        self.properties = None
        self.cooled = True
        self.cooling = False

        # Get the model and port number
        model = config.get('model')
        port = config.get('port')
        name = config.get('name')

        self.model = model
        self.port = port
        self.name = name

        self._connected = False

        self.last_start_time = None

        self.logger.info('Camera {} created on {}'.format(self.name, self.config.get('port')))

##################################################################################################
# Methods
##################################################################################################

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        """
        return NotImplementedError()


class AbstractIndiCamera(AbstractCamera, PanIndiDevice):

    """ Abstract Camera class that uses INDI.

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """
    pass

    def __init__(self, config):
        super().__init__(config)


class AbstractGPhotoCamera(AbstractCamera):

    """ Abstract camera class that uses gphoto2 interaction

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, config):
        super().__init__(config)

        self._gphoto2 = shutil.which('gphoto2')
        assert self._gphoto2 is not None, error.PanError("Can't find gphoto2")

        self.logger.info('GPhoto2 camera {} created on {}'.format(self.name, self.config.get('port')))

        # Setup a holder for the process
        self._proc = None

    def command(self, cmd):
        """ Run gphoto2 command """

        if self._proc:
            raise error.InvalidCommand("Command already running")
        else:
            # Build the command.
            run_cmd = [self._gphoto2, '--port', self.port]
            run_cmd.extend(listify(cmd))

            self.logger.debug("gphoto2 command: {}".format(run_cmd))

            try:
                self._proc = subprocess.Popen(
                    run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            except OSError as e:
                raise error.InvalidCommand("Can't send command to gphoto2. {} \t {}".format(e, run_cmd))
            except ValueError as e:
                raise error.InvalidCommand("Bad parameters to gphoto2. {} \t {}".format(e, run_cmd))
            except Exception as e:
                raise error.PanError(e)

    def get_command_result(self):
        """ Get the output from the command """

        self.logger.debug("Getting output from proc {}".format(self._proc.pid))

        try:
            outs, errs = self._proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            outs, errs = self._proc.communicate()

        self._proc = None

        # self.logger.debug("Output from command: {}".format(outs))
        return outs

    def set_property(self, prop, val):
        """ Set a property on the camera """
        set_cmd = ['--set-config', '{}={}'.format(prop, val)]

        self.command(set_cmd)

        # Forces the command to wait
        self.get_command_result()

    def get_property(self, prop):
        """ Gets a property from the camera """
        set_cmd = ['--get-config', '{}'.format(prop)]

        output = self.command(set_cmd)
        return output

    def load_properties(self):
        ''' Load properties from the camera
        Reads all the configuration properties available via gphoto2 and populates
        a local list with these entries.
        '''
        self.logger.debug('Get All Properties')
        command = ['--list-all-config']

        self.properties = self.parse_config(self.command(command))

        if self.properties:
            self.logger.debug('  Found {} properties'.format(len(self.properties)))
        else:
            self.logger.warning('  Could not determine properties.')

    def parse_config(self, lines):
        yaml_string = ''
        for line in lines:
            IsID = len(line.split('/')) > 1
            IsLabel = re.match('^Label:\s(.*)', line)
            IsType = re.match('^Type:\s(.*)', line)
            IsCurrent = re.match('^Current:\s(.*)', line)
            IsChoice = re.match('^Choice:\s(\d+)\s(.*)', line)
            IsPrintable = re.match('^Printable:\s(.*)', line)
            IsHelp = re.match('^Help:\s(.*)', line)
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
            elif IsHelp:
                line = '  {}'.format(line)
            elif IsID:
                line = '- ID: {}'.format(line)
            elif line == '':
                continue
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

    def list_connected_cameras(self):
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
                # camera_name = camera_match.group(1).strip()
                port = camera_match.group(2).strip()
                ports.append(port)

        return ports
