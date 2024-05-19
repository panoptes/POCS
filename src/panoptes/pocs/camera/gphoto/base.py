import re
import subprocess
import time
from abc import ABC
from typing import List, Dict, Union

from panoptes.utils import error
from panoptes.utils.images import cr2 as cr2_utils
from panoptes.utils.serializers import from_yaml
from panoptes.utils.utils import listify

from panoptes.pocs.camera import AbstractCamera, get_gphoto2_cmd

file_save_re = re.compile(r'Saving file as (.*)')


class AbstractGPhotoCamera(AbstractCamera, ABC):  # pragma: no cover

    """ Abstract camera class that uses gphoto2 interaction.

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

        # Set up a holder for the exposure process.
        self._command_proc = None

        self.logger.info(f'GPhoto2 camera {self.name} created on {self.port}')

    @property
    def temperature(self):
        return None

    @property
    def target_temperature(self):
        return None

    @property
    def cooling_power(self):
        return None

    @AbstractCamera.uid.getter
    def uid(self) -> str:
        """ A six-digit serial number for the camera """
        return self._serial_number[0:6]

    def connect(self):
        raise NotImplementedError

    @property
    def is_exposing(self):
        if self._command_proc is not None and self._command_proc.poll() is not None:
            self._is_exposing_event.clear()

        return self._is_exposing_event.is_set()

    def process_exposure(self, metadata, **kwargs):
        """Converts the CR2 to FITS then processes image."""
        # Wait for exposure to complete. Timeout handled by exposure thread.
        while self.is_exposing:
            time.sleep(0.5)

        metadata['filepath'] = metadata['filepath'].replace('.cr2', '.fits')
        super(AbstractGPhotoCamera, self).process_exposure(metadata, **kwargs)
        self._command_proc = None

    def command(self, cmd: Union[List[str], str], check_exposing: bool = True):
        """ Run gphoto2 command. """

        # Test to see if there is a running command already
        if self.is_exposing and check_exposing:
            raise error.InvalidCommand("Command already running")
        else:
            # Build the command.
            run_cmd = [get_gphoto2_cmd()]
            if self.port is not None:
                run_cmd.extend(['--port', self.port])
            run_cmd.extend(listify(cmd))

            self.logger.debug(f"gphoto2 command: {run_cmd!r}")

            try:
                self._command_proc = subprocess.Popen(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                self.logger.debug(f'Started command on proc={self._command_proc.pid}')
            except OSError as e:
                raise error.InvalidCommand(f"Can't send command to gphoto2. {e} \t {run_cmd}")
            except ValueError as e:
                raise error.InvalidCommand(f"Bad parameters to gphoto2. {e} \t {run_cmd}")
            except Exception as e:
                raise error.PanError(e)

    def get_command_result(self, timeout: float = 10) -> Union[List[str], None]:
        """ Get the output from the command.

        Accepts a `timeout` param for communicating with the process.

        Returns a list of strings corresponding to the output from the gphoto2
        camera or `None` if no command has been specified.
        """
        if self._command_proc is None:
            return None

        self.logger.debug(f"Getting output from proc {self._command_proc.pid}")

        try:
            outs, errs = self._command_proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.debug(f"Timeout while waiting. Killing process {self._command_proc.pid}")
            self._command_proc.kill()
            outs, errs = self._command_proc.communicate()

        self.logger.trace(f'gphoto2 output: {outs=!r}')
        if errs != '':
            self.logger.warning(f'gphoto2 error: {errs!r}')

        if isinstance(outs, str):
            outs = outs.split('\n')

        self._command_proc = None

        return outs

    def set_property(self, prop: str, val: Union[str, int], is_value: bool = False, is_index: bool = False):
        """ Set a property on the camera.

        Args:
            prop (str): The property to set.
            val (str, int): The value to set the property to.
            is_value (bool): If True, then the value is a literal value. Default False.
            is_index (bool): If True, then the value is an index. Default False.

        Raises:
            ValueError: If the property is not found.
        """
        self.logger.debug(f'Setting {prop=} to {val=}')
        if is_index:
            set_cmd = ['--set-config-index', f'{prop}={val}']
        elif is_value:
            set_cmd = ['--set-config-value', f'{prop}={val}']
        else:
            set_cmd = ['--set-config', f'{prop}="{val}"']

        self.command(set_cmd)

        # Forces the command to wait
        self.get_command_result()

    def set_properties(self, prop2index: Dict[str, int] = None, prop2value: Dict[str, str] = None):
        """ Sets a number of properties all at once, by index or value.

        Args:
            prop2index (dict or None): A dict with keys corresponding to the property to
                be set and values corresponding to the index option.
            prop2value (dict or None): A dict with keys corresponding to the property to
                be set and values corresponding to the literal value.
        """
        if prop2index:
            for prop, val in prop2index.items():
                try:
                    self.set_property(prop, val, is_index=True)
                except Exception:
                    self.logger.debug(f'Skipping {prop=} {val=}')

        if prop2value:
            for prop, val in prop2value.items():
                try:
                    self.set_property(prop, val, is_value=True)
                except Exception:
                    self.logger.debug(f'Skipping {prop=} {val=}')

    def get_property(self, prop: str) -> str:
        """ Gets a property from the camera """
        set_cmd = ['--get-config', f'{prop}']

        self.command(set_cmd)
        result = self.get_command_result()

        output = ''
        for line in result:
            match = re.match(r'Current:\s*(.*)', line)
            if match:
                output = match.group(1)

        return output

    def load_properties(self) -> dict:
        """ Load properties from the camera.

        Reads all the configuration properties available via gphoto2 and returns
        as dictionary.
        """
        self.logger.debug('Getting all properties for gphoto2 camera')
        self.command(['--list-all-config'])
        lines = self.get_command_result()

        properties = {}
        yaml_string = ''

        for line in lines:
            is_id = len(line.split('/')) > 1
            is_label = re.match(r'^Label:\s*(.*)', line)
            is_type = re.match(r'^Type:\s*(.*)', line)
            is_readonly = re.match(r'^Readonly:\s*(.*)', line)
            is_current = re.match(r'^Current:\s*(.*)', line)
            is_choice = re.match(r'^Choice:\s*(\d+)\s*(.*)', line)
            is_printable = re.match(r'^Printable:\s*(.*)', line)
            is_help = re.match(r'^Help:\s*(.*)', line)

            if is_label or is_type or is_current or is_readonly:
                line = f'  {line}'
            elif is_choice:
                if int(is_choice.group(1)) == 0:
                    line = f'  Choices:\n    {int(is_choice.group(1)):d}: {is_choice.group(2)}'
                else:
                    line = f'    {int(is_choice.group(1)):d}: {is_choice.group(2)}'
            elif is_printable:
                line = f'  {line}'
            elif is_help:
                line = f'  {line}'
            elif is_id:
                line = f'- ID: {line}'
            elif line == '' or line == 'END':
                continue
            else:
                self.logger.debug(f'Line not parsed: {line}')

            yaml_string += f'{line}\n'

        self.logger.debug(yaml_string)
        properties_list = from_yaml(yaml_string)

        if isinstance(properties_list, list):
            for prop in properties_list:
                if prop['Label']:
                    properties[prop['Label']] = prop
        else:
            properties = properties_list

        return properties

    def _poll_exposure(self, readout_args, exposure_time, timeout=None, interval=0.01):
        """Check the command output from gphoto2 for polling.

        This will essentially block until the camera is done exposing, which means
        the super call should not have to wait.
        """
        self.logger.debug(f'Calling get_command_result from base gphoto2 for {self}')
        # Wait for and clear the _command_proc.
        outs = self.get_command_result(timeout)
        self.logger.debug(f'Camera response for {self}: {outs}')
        self._is_exposing_event.clear()
        self.logger.debug(f'Exposing event cleared for {self}')

        super()._poll_exposure(readout_args, exposure_time, timeout=timeout, interval=interval)

    def _readout(self, filename, headers, *args, **kwargs):
        self.logger.debug(f'Reading Canon DSLR exposure for {filename=}')
        try:
            self.logger.debug(f"Converting CR2 -> FITS: {filename}")
            fits_path = cr2_utils.cr2_to_fits(filename, headers=headers, remove_cr2=False)
        except TimeoutError:
            self.logger.error(f'Error processing exposure for {filename} on {self}')
        finally:
            self._readout_complete = True

    def _set_target_temperature(self, target):
        return None

    def _set_cooling_enabled(self, enable):
        return None

    @classmethod
    def start_tether(cls, port, filename_pattern: str = '%Y%m%dT%H%M%S.%C'):
        """Start a tether for gphoto2 auto-download on given port using filename pattern."""
        print(f'Starting gphoto2 tether for {port=} using {filename_pattern=}')

        full_command = [get_gphoto2_cmd(),
                        '--port', port,
                        '--filename', filename_pattern,
                        '--capture-tethered']

        # Start tether process.
        process = subprocess.Popen(
            full_command,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE
        )
        print(f'gphoto2 tether started on {port=} on {process.pid=}')

        try:
            process.wait()
        except KeyboardInterrupt:
            print(f'Stopping tether on {port=}')

    @classmethod
    def gphoto_file_download(
        cls,
        port: str,
        filename_pattern: str,
        only_new: bool = True
    ):
        """Downloads (newer) files from the camera on the given port using the filename pattern."""
        print(f'Starting gphoto2 download for {port=} using {filename_pattern=}')
        command = [get_gphoto2_cmd(),
                   '--port', port,
                   '--filename', filename_pattern,
                   '--get-all-files',
                   '--recurse']
        if only_new:
            command.append('--new')

        completed_proc = subprocess.run(command, capture_output=True)
        success = completed_proc.returncode >= 0

        filenames = list()
        if success:
            output = completed_proc.stdout.decode('utf-8').split('\n')

            for line in output:
                file_match = file_save_re.match(line)
                if file_match is not None:
                    fn = file_match.group(1).strip()
                    print(f'Found match {fn}')
                    filenames.append(fn)

        return filenames
