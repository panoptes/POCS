# from ..utils.indi import PanIndiDevice

from ..utils.logger import get_logger
from ..utils import error
from ..utils import listify

import re
import shutil
import subprocess
import yaml


class AbstractCamera(object):

    """ Base class for all cameras """

    def __init__(self, config, **kwargs):
        self.logger = get_logger(self)
        self.config = config

        self.properties = None
        self.cooled = True
        self.cooling = False

        self._image_dir = config.get('image_dir')

        # Get the model and port number
        model = config.get('model')
        port = config.get('port')
        name = config.get('name')

        self.model = model
        self.port = port
        self.name = name

        self.is_primary = config.get('primary', False)
        self.is_guide = config.get('guide', False)

        self._connected = False
        self._serial_number = 'XXXXXX'

        self._last_start_time = None  # For constructing file name

        self.logger.debug('Camera {} created on {}'.format(self.name, self.config.get('port')))

##################################################################################################
# Properties
##################################################################################################

    @property
    def uid(self):
        return self._serial_number[0:6]

##################################################################################################
# Methods
##################################################################################################

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        """
        return NotImplementedError()

    def take_exposure(self, **kwargs):
        return NotImplementedError()


class AbstractGPhotoCamera(AbstractCamera):

    """ Abstract camera class that uses gphoto2 interaction

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)

        self._gphoto2 = shutil.which('gphoto2')
        assert self._gphoto2 is not None, error.PanError("Can't find gphoto2")

        self.logger.debug('GPhoto2 camera {} created on {}'.format(self.name, self.config.get('port')))

        # Setup a holder for the process
        self._proc = None

    def command(self, cmd):
        """ Run gphoto2 command """

        # Test to see if there is a running command already
        if self._proc and self._proc.poll():
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

    def get_command_result(self, timeout=10):
        """ Get the output from the command """

        self.logger.debug("Getting output from proc {}".format(self._proc.pid))

        try:
            outs, errs = self._proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.debug("Timeout while waiting. Killing process {}".format(self._proc.pid))
            self._proc.kill()
            outs, errs = self._proc.communicate()

        self._proc = None

        return outs

    def wait_for_command(self, timeout=10):
        """ Wait for the given command to end

        This method merely waits for a subprocess to complete but doesn't attempt to communicate
        with the process (see `get_command_result` for that).
        """
        self.logger.debug("Waiting for proc {}".format(self._proc.pid))

        try:
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.warning("Timeout expired for PID {}".format(self._proc.pid))

        self._proc = None

    def set_property(self, prop, val):
        """ Set a property on the camera """
        set_cmd = ['--set-config', '{}={}'.format(prop, val)]

        self.command(set_cmd)

        # Forces the command to wait
        self.get_command_result()

    def get_property(self, prop):
        """ Gets a property from the camera """
        set_cmd = ['--get-config', '{}'.format(prop)]

        self.command(set_cmd)
        result = self.get_command_result()

        output = ''
        for line in result.split('\n'):
            match = re.match('Current:\s(.*)', line)
            if match:
                output = match.group(1)

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


# class AbstractIndiCamera(AbstractCamera, PanIndiDevice):

#     """ Abstract Camera class that uses INDI.

#     Args:
#         config(Dict):   Config key/value pairs, defaults to empty dict.
#     """
#     pass

#     def __init__(self, config, **kwargs):
#         super().__init__(config, **kwargs)
