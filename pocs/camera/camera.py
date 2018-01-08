from pocs import PanBase

from pocs.utils import error
from pocs.utils import listify
from pocs.utils import load_module
from pocs.utils import images

from pocs.focuser import AbstractFocuser

from astropy.io import fits

import re
import shutil
import subprocess
import yaml
import os


class AbstractCamera(PanBase):

    """ Base class for all cameras """

    def __init__(self,
                 name='Generic Camera',
                 model='simulator',
                 port=None,
                 primary=False,
                 focuser=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            self._image_dir = self.config['directories']['images']
        except KeyError:
            self.logger.error("No images directory. Set image_dir in config")

        self.model = model
        self.port = port
        self.name = name

        self.is_primary = primary

        self._connected = False
        self._serial_number = 'XXXXXX'
        self._readout_time = kwargs.get('readout_time', 5.0)
        self._file_extension = kwargs.get('file_extension', 'fits')
        self.filter_type = 'RGGB'

        self.properties = None
        self._current_observation = None

        if focuser:
            if isinstance(focuser, AbstractFocuser):
                self.logger.debug("Focuser received: {}".format(focuser))
                self.focuser = focuser
                self.focuser.camera = self
            elif isinstance(focuser, dict):
                try:
                    module = load_module('pocs.focuser.{}'.format(focuser['model']))
                except AttributeError as err:
                    self.logger.critical("Couldn't import Focuser module {}!".format(module))
                    raise err
                else:
                    self.focuser = module.Focuser(**focuser, camera=self)
                    self.logger.debug("Focuser created: {}".format(self.focuser))
            else:
                # Should have been passed either a Focuser instance or a dict with Focuser
                # configuration. Got something else...
                self.logger.error(
                    "Expected either a Focuser instance or dict, got {}".format(focuser))
                self.focuser = None
        else:
            self.focuser = None

        self.logger.debug('Camera created: {}'.format(self))

##################################################################################################
# Properties
##################################################################################################

    @property
    def uid(self):
        """ A six-digit serial number for the camera """
        return self._serial_number[0:6]

    @property
    def is_connected(self):
        """ Is the camera available vai gphoto2 """
        return self._connected

    @property
    def readout_time(self):
        """ Readout time for the camera in seconds """
        return self._readout_time

    @property
    def file_extension(self):
        """ File extension for images saved by camera """
        return self._file_extension

    @property
    def CCD_temp(self):
        """
        Get current temperature of the camera's image sensor.

        Note: this only needs to be implemented for cameras which can provided this information,
        e.g. those with cooled image sensors.
        """
        raise NotImplementedError

    @property
    def CCD_set_point(self):
        """
        Get current value of the CCD set point, the target temperature for the camera's
        image sensor cooling control.

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError

    @CCD_set_point.setter
    def CCD_set_point(self, set_point):
        """
        Set value of the CCD set point, the target temperature for the camera's image sensor
        cooling control.

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError

    @property
    def CCD_cooling_enabled(self):
        """
        Get current status of the camera's image sensor cooling system (enabled/disabled).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError

    @property
    def CCD_cooling_power(self):
        """
        Get current power level of the camera's image sensor cooling system (typically as
        a percentage of the maximum).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError

##################################################################################################
# Methods
##################################################################################################

    def take_observation(self, *args, **kwargs):
        raise NotImplementedError

    def take_exposure(self, *args, **kwargs):
        raise NotImplementedError

    def process_exposure(self, *args, **kwargs):
        raise NotImplementedError

    def autofocus(self,
                  seconds=None,
                  focus_range=None,
                  focus_step=None,
                  thumbnail_size=None,
                  keep_files=None,
                  take_dark=None,
                  merit_function='vollath_F4',
                  merit_function_kwargs={},
                  coarse=False,
                  plots=True,
                  blocking=False,
                  *args, **kwargs):
        """
        Focuses the camera using the specified merit function. Optionally
        performs a coarse focus first before performing the default fine focus.
        The expectation is that coarse focus will only be required for first use
        of a optic to establish the approximate position of infinity focus and
        after updating the intial focus position in the config only fine focus
        will be required.

        Args:
            seconds (optional): Exposure time for focus exposures, if not
                specified will use value from config.
            focus_range (2-tuple, optional): Coarse & fine focus sweep range, in
                encoder units. Specify to override values from config.
            focus_step (2-tuple, optional): Coarse & fine focus sweep steps, in
                encoder units. Specify to override values from config.
            thumbnail_size (optional): Size of square central region of image to
                use, default 500 x 500 pixels.
            keep_files (bool, optional): If True will keep all images taken
                during focusing. If False (default) will delete all except the
                first and last images from each focus run.
            take_dark (bool, optional): If True will attempt to take a dark frame
                before the focus run, and use it for dark subtraction and hot
                pixel masking, default True.
            merit_function (str/callable, optional): Merit function to use as a
                focus metric.
            merit_function_kwargs (dict, optional): Dictionary of additional
                keyword arguments for the merit function.
            coarse (bool, optional): Whether to begin with coarse focusing,
                default False
            plots (bool, optional: Whether to write focus plots to images folder,
                default True.
            blocking (bool, optional): Whether to block until autofocus complete,
                default False

        Returns:
            threading.Event: Event that will be set when autofocusing is complete
        """
        if self.focuser is None:
            self.logger.error("Camera must have a focuser for autofocus!")
            raise AttributeError

        return self.focuser.autofocus(seconds=seconds,
                                      focus_range=focus_range,
                                      focus_step=focus_step,
                                      keep_files=keep_files,
                                      take_dark=take_dark,
                                      thumbnail_size=thumbnail_size,
                                      merit_function=merit_function,
                                      merit_function_kwargs=merit_function_kwargs,
                                      coarse=coarse,
                                      plots=plots,
                                      blocking=blocking,
                                      *args, **kwargs)

    def get_thumbnail(self, seconds, file_path, thumbnail_size, keep_file=False, *args, **kwargs):
        """
        Takes an image and returns a thumbnail.

        Takes an image, grabs the data, deletes the FITS file and
        returns a thumbnail from the centre of the image.

        Args:
            seconds (astropy.units.Quantity): exposure time, Quantity or numeric type in seconds.
            file_path (str): path to (temporarily) save the image file to.
            thumbnail_size (int): size of the square region of the centre of the image to return.
            keep_file (bool, optional): if True the image file will be deleted, if False it will
                be kept.
            *args, **kwargs: passed to the take_exposure() method
        """
        exposure = self.take_exposure(seconds, filename=file_path, *args, **kwargs)
        exposure.wait()
        image = fits.getdata(file_path)
        if not keep_file:
            os.unlink(file_path)
        thumbnail = images.crop_data(image, box_width=thumbnail_size)
        return thumbnail

    def __str__(self):
        try:
            return "{} ({}) on {} with {}".format(
                self.name,
                self.uid,
                self.port,
                self.focuser.name
            )
        except AttributeError:
            return "{} ({}) on {}".format(self.name, self.uid, self.port)


class AbstractGPhotoCamera(AbstractCamera):  # pragma: no cover

    """ Abstract camera class that uses gphoto2 interaction

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

        self._gphoto2 = shutil.which('gphoto2')
        assert self._gphoto2 is not None, error.PanError("Can't find gphoto2")

        self.logger.debug('GPhoto2 camera {} created on {}'.format(self.name, self.port))

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

        self.properties = self.parse_config(self.command(command))

        if self.properties:
            self.logger.debug('  Found {} properties'.format(len(self.properties)))
        else:
            self.logger.warning('  Could not determine properties.')

    def parse_config(self, lines):
        yaml_string = ''
        for line in lines:
            IsID = len(line.split('/')) > 1
            IsLabel = re.match(r'^Label:\s*(.*)', line)
            IsType = re.match(r'^Type:\s*(.*)', line)
            IsCurrent = re.match(r'^Current:\s*(.*)', line)
            IsChoice = re.match(r'^Choice:\s*(\d+)\s*(.*)', line)
            IsPrintable = re.match(r'^Printable:\s*(.*)', line)
            IsHelp = re.match(r'^Help:\s*(.*)', line)
            if IsLabel:
                line = '  {}'.format(line)
            elif IsType:
                line = '  {}'.format(line)
            elif IsCurrent:
                line = '  {}'.format(line)
            elif IsChoice:
                if int(IsChoice.group(1)) == 0:
                    line = '  Choices:\n    {}: {:d}'.format(
                        IsChoice.group(2), int(IsChoice.group(1)))
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
