import re
import shutil
import subprocess

from panoptes.pocs.camera import AbstractCamera
from panoptes.utils import error
from panoptes.utils.serializers import from_yaml
from panoptes.utils.utils import listify


def parse_config(lines):  # pragma: no cover
    yaml_string = ''
    for line in lines:
        IsID = len(line.split('/')) > 1
        IsLabel = re.match(r'^Label:\s*(.*)', line)
        IsType = re.match(r'^Type:\s*(.*)', line)
        IsCurrent = re.match(r'^Current:\s*(.*)', line)
        IsChoice = re.match(r'^Choice:\s*(\d+)\s*(.*)', line)
        IsPrintable = re.match(r'^Printable:\s*(.*)', line)
        IsHelp = re.match(r'^Help:\s*(.*)', line)
        if IsLabel or IsType or IsCurrent:
            line = f'  {line}'
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
            print(f'Line not parsed: {line}')
        yaml_string += f'{line}\n'
    properties_list = from_yaml(yaml_string)
    if isinstance(properties_list, list):
        properties = {}
        for property in properties_list:
            if property['Label']:
                properties[property['Label']] = property
    else:
        properties = properties_list
    return properties


class AbstractGPhotoCamera(AbstractCamera):  # pragma: no cover

    """ Abstract camera class that uses gphoto2 interaction

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

        self.properties = None

        self._gphoto2 = shutil.which('gphoto2')
        assert self._gphoto2 is not None, error.PanError("Can't find gphoto2")

        self.logger.debug('GPhoto2 camera {} created on {}'.format(self.name, self.port))

        # Setup a holder for the process
        self._proc = None

        # Explicitly set holders for some of the hardware subcomponents until
        # TODO fix the setting of the attribute.
        self.focuser = None
        self.filterwheel = None

    @AbstractCamera.uid.getter
    def uid(self):
        """ A six-digit serial number for the camera """
        return self._serial_number[0:6]

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
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    shell=False
                )
            except OSError as e:
                raise error.InvalidCommand(
                    "Can't send command to gphoto2. {} \t {}".format(
                        e, run_cmd))
            except ValueError as e:
                raise error.InvalidCommand(
                    "Bad parameters to gphoto2. {} \t {}".format(e, run_cmd))
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

    def set_properties(self, prop2index, prop2value):
        """ Sets a number of properties all at once, by index or value.

        Args:
            prop2index (dict): A dict with keys corresponding to the property to
            be set and values corresponding to the index option
            prop2value (dict): A dict with keys corresponding to the property to
            be set and values corresponding to the literal value
        """
        set_cmd = list()
        for prop, val in prop2index.items():
            set_cmd.extend(['--set-config-index', '{}={}'.format(prop, val)])
        for prop, val in prop2value.items():
            set_cmd.extend(['--set-config-value', '{}={}'.format(prop, val)])

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
            match = re.match(r'Current:\s*(.*)', line)
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

        self.properties = parse_config(self.command(command))

        if self.properties:
            self.logger.debug('  Found {} properties'.format(len(self.properties)))
        else:
            self.logger.warning('  Could not determine properties.')
