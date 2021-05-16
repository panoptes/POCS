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
        is_id = len(line.split('/')) > 1
        is_label = re.match(r'^Label:\s*(.*)', line)
        is_type = re.match(r'^Type:\s*(.*)', line)
        is_current = re.match(r'^Current:\s*(.*)', line)
        is_choice = re.match(r'^Choice:\s*(\d+)\s*(.*)', line)
        is_printable = re.match(r'^Printable:\s*(.*)', line)
        is_help = re.match(r'^Help:\s*(.*)', line)
        if is_label or is_type or is_current:
            line = f'  {line}'
        elif is_choice:
            if int(is_choice.group(1)) == 0:
                line = f'  Choices:\n    {is_choice.group(2)}: {int(is_choice.group(1)):d}'
            else:
                line = f'    {is_choice.group(2)}: {int(is_choice.group(1)):d}'
        elif is_printable:
            line = f'  {line}'
        elif is_help:
            line = f'  {line}'
        elif is_id:
            line = f'- ID: {line}'
        elif line == '':
            continue
        else:
            print(f'Line not parsed: {line}')
        yaml_string += f'{line}\n'
    properties_list = from_yaml(yaml_string)
    if isinstance(properties_list, list):
        properties = {}
        for prop in properties_list:
            if prop['Label']:
                properties[prop['Label']] = prop
    else:
        properties = properties_list
    return properties


class AbstractGPhotoCamera(AbstractCamera):  # pragma: no cover

    """ Abstract camera class that uses gphoto2 interaction

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    @property
    def egain(self):
        return None

    def connect(self):
        raise NotImplementedError

    def _start_exposure(self, seconds=None, filename=None, dark=False, header=None, *args,
                        **kwargs):
        raise NotImplementedError

    def _readout(self, filename=None, **kwargs):
        raise NotImplementedError

    @property
    def bit_depth(self):
        return 14

    @property
    def temperature(self):
        return None

    @property
    def target_temperature(self):
        return None

    @property
    def cooling_power(self):
        return None

    def _set_target_temperature(self, target):
        return None

    def _set_cooling_enabled(self, enable):
        return None

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

        self.properties = None

        self._gphoto2 = shutil.which('gphoto2')
        assert self._gphoto2 is not None, error.PanError("Can't find gphoto2")

        self.logger.debug(f'GPhoto2 camera {self.name} created on {self.port}')

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

            self.logger.debug(f"gphoto2 command: {run_cmd}")

            try:
                self._proc = subprocess.Popen(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    shell=False
                )
            except OSError as e:
                raise error.InvalidCommand(f"Can't send command to gphoto2. {e} \t {run_cmd}")
            except ValueError as e:
                raise error.InvalidCommand(f"Bad parameters to gphoto2. {e} \t {run_cmd}")
            except Exception as e:
                raise error.PanError(e)

    def get_command_result(self, timeout=10):
        """ Get the output from the command """

        self.logger.debug(f"Getting output from proc {self._proc.pid}")

        try:
            outs, errs = self._proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.debug(f"Timeout while waiting. Killing process {self._proc.pid}")
            self._proc.kill()
            outs, errs = self._proc.communicate()

        self._proc = None

        return outs

    def wait_for_command(self, timeout=10):
        """ Wait for the given command to end

        This method merely waits for a subprocess to complete but doesn't attempt to communicate
        with the process (see `get_command_result` for that).
        """
        self.logger.debug(f"Waiting for proc {self._proc.pid}")

        try:
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout expired for PID {self._proc.pid}")

        self._proc = None

    def set_property(self, prop, val):
        """ Set a property on the camera """
        set_cmd = ['--set-config', f'{prop}={val}']

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
            set_cmd.extend(['--set-config-index', f'{prop}={val}'])
        for prop, val in prop2value.items():
            set_cmd.extend(['--set-config-value', f'{prop}={val}'])

        self.command(set_cmd)

        # Forces the command to wait
        self.get_command_result()

    def get_property(self, prop):
        """ Gets a property from the camera """
        set_cmd = ['--get-config', f'{prop}']

        self.command(set_cmd)
        result = self.get_command_result()

        output = ''
        for line in result.split('\n'):
            match = re.match(r'Current:\s*(.*)', line)
            if match:
                output = match.group(1)

        return output

    def load_properties(self):
        """ Load properties from the camera
        Reads all the configuration properties available via gphoto2 and populates
        a local list with these entries.
        """
        self.logger.debug('Get All Properties')
        command = ['--list-all-config']

        self.properties = parse_config(self.command(command))

        if self.properties:
            self.logger.debug(f'Found {len(self.properties)} properties')
        else:
            self.logger.warning('Could not determine properties.')
