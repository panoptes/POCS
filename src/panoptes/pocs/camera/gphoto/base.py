import re
import shutil
import subprocess
from abc import ABC
from threading import Event
from threading import Timer
from typing import List, Dict, Union

from panoptes.utils import error
from panoptes.utils.utils import listify
from panoptes.utils.serializers import from_yaml
from panoptes.utils.images import cr2 as cr2_utils
from panoptes.utils.time import CountdownTimer
from panoptes.pocs.camera import AbstractCamera


class AbstractGPhotoCamera(AbstractCamera, ABC):  # pragma: no cover

    """ Abstract camera class that uses gphoto2 interaction.

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

        # Setup a holder for the exposure process.
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

    def take_observation(self, observation, headers=None, filename=None, *args, **kwargs):
        """Take an observation.

        Gathers various header information, sets the file path, and calls
        `take_exposure`. Also creates a `threading.Event` object and a
        `threading.Timer` object. The timer calls `process_exposure` after the
        set amount of time is expired (`observation.exptime + self.readout_time`).

        Note:
            If a `filename` is passed in it can either be a full path that includes
            the extension, or the basename of the file, in which case the directory
            path and extension will be added to the `filename` for output

        Args:
            observation (~pocs.scheduler.observation.Observation): Object
                describing the observation
            headers (dict): Header data to be saved along with the file
            filename (str, optional): Filename for saving, defaults to ISOT time stamp
            **kwargs (dict): Optional keyword arguments (`exptime`)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        observation_event = Event()

        exptime, file_path, image_id, metadata = self._setup_observation(observation,
                                                                         headers,
                                                                         filename,
                                                                         **kwargs)

        self.take_exposure(seconds=exptime, filename=file_path)

        # Add most recent exposure to list
        if self.is_primary:
            if 'POINTING' in headers:
                observation.pointing_images[image_id] = file_path.replace('.cr2', '.fits')
            else:
                observation.exposure_list[image_id] = file_path.replace('.cr2', '.fits')

        # Process the image after a set amount of time
        wait_time = exptime + self.readout_time

        t = Timer(wait_time, self.process_exposure, (metadata, observation_event))
        t.name = f'{self.name}Thread'
        t.start()

        return observation_event

    def command(self, cmd: Union[List[str], str]):
        """ Run gphoto2 command. """

        # Test to see if there is a running command already
        if self._command_proc and self._command_proc.poll():
            raise error.InvalidCommand("Command already running")
        else:
            # Build the command.
            run_cmd = [shutil.which('gphoto2')]
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
            self.logger.error(f'gphoto2 error: {errs!r}')

        if isinstance(outs, str):
            outs = outs.split('\n')

        self._command_proc = None

        return outs

    def set_property(self, prop: str, val: Union[str, int]):
        """ Set a property on the camera """
        set_cmd = ['--set-config', f'{prop}={val}']

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
        set_cmd = list()
        if prop2index:
            for prop, val in prop2index.items():
                set_cmd.extend(['--set-config-index', f'{prop}={val}'])

        if prop2value:
            for prop, val in prop2value.items():
                set_cmd.extend(['--set-config-value', f'{prop}={val}'])

        self.command(set_cmd)

        # Forces the command to wait
        self.get_command_result()

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

    def _poll_exposure(self, readout_args, *args, **kwargs):
        timer = CountdownTimer(duration=self._timeout)
        try:
            try:
                # See if the command has finished.
                while self._command_proc.poll() is None:
                    # Sleep if not done yet.
                    timer.sleep(max_sleep=1, log_level='TRACE')
            except subprocess.TimeoutExpired:
                self.logger.warning(f'Timeout on exposure process for {self.name}')
                self._command_proc.kill()
                outs, errs = self._command_proc.communicate(timeout=10)
                if errs is not None and errs > '':
                    self.logger.error(f'Camera exposure errors: {errs}')
        except (RuntimeError, error.PanError) as err:
            # Error returned by driver at some point while polling
            self.logger.error(f'Error while waiting for exposure on {self}: {err}')
            self._command_proc = None
            raise err
        else:
            # Camera type specific readout function
            self._readout(*readout_args)
        finally:
            self.logger.debug(f'Setting exposure event for {self.name}')
            self._is_exposing_event.clear()  # Make sure this gets set regardless of readout errors

    def _readout(self, cr2_path=None, info=None):
        """Reads out the image as a CR2 and converts to FITS"""
        self.logger.debug(f"Converting CR2 -> FITS: {cr2_path}")
        fits_path = cr2_utils.cr2_to_fits(cr2_path, headers=info, remove_cr2=False)
        return fits_path

    def _process_fits(self, file_path, info):
        """
        Add FITS headers from info the same as images.cr2_to_fits()
        """
        file_path = file_path.replace('.cr2', '.fits')
        return super()._process_fits(file_path, info)

    def _set_target_temperature(self, target):
        return None

    def _set_cooling_enabled(self, enable):
        return None
