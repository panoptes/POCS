from .. import PanBase

from ..utils import error
from ..utils import listify
from ..utils import load_module
from ..utils import images
from ..utils import current_time

from ..focuser.focuser import AbstractFocuser

from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.modeling import models, fitting

import numpy as np

import matplotlib.pyplot as plt

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
                 focus_port=None,
                 focus_initial=None,
                 autofocus_range=None,
                 autofocus_step=None,
                 autofocus_seconds=None,
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
                if focus_port:
                    self.logger.warning("Passed Focuser object but also tried to specify port!")
                if focus_initial:
                    self.focuser.position = focus_initial
                if autofocus_range:
                    self.focuser.autofocus_range = (int(autofocus_range[0]), int(autofocus_range[1]))
                if autofocus_step:
                    self.focuser.autofocus_step = (int(autofocus_step[0]), int(autofocus_step[1]))
                if autofocus_seconds:
                    self.focuse.autofocus_seconds = autofocus_seconds
            else:
                try:
                    module = load_module('pocs.focuser.{}'.format(focuser))
                except AttributeError as err:
                    self.logger.critical("Couldn't import Focuser module {}!".format(module))
                    raise err
                else:
                    self.focuser = module.Focuser(port=focus_port,
                                                  camera=self,
                                                  initial_position=focus_initial,
                                                  autofocus_range=autofocus_range,
                                                  autofocus_step=autofocus_step,
                                                  autofocus_seconds=autofocus_seconds)
                    self.logger.debug("Focuser created: {}".format(self.focuser))
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

    def autofocus(self, seconds=None, focus_range=None, focus_step=None,
                  coarse=False, thumbnail_size=500, plots=False, *args, **kwargs):
        """
        
        """
        try:
            assert self.focuser.is_connected 
        except AttributeError:
            self.logger.error('Attempted to autofocus but camera {} has no focuser!'.format(self))
            return
        except AssertionError:
            self.logger.error('Attempted to autofocus but camera {} focuser is not connected!'.format(self))
            return

        if not focus_range:
            if not self.focuser.autofocus_range:
                self.logger.error("No focus_range specified, aborting autofocus of {}!".format(self))
                return
            else:
                focus_range = self.focuser.autofocus_range

        if not focus_step:
            if not self.focuser.autofocus_step:
                self.logger.error("No focus_step specified, aborting autofocus of {}!".format(self))
                return
            else:
                focus_step = self.focuser.autofocus_step

        if not seconds:
            if not self.focuser.autofocus_seconds:
                self.logger.error("No focus exposure time specified, aborting autofocus of {}!".format(self))
                return
            else:
                seconds = self.focuser.autofocus_seconds

        initial_focus = self.focuser.position
        self.logger.debug("Beginning autofocus of {} - initial focus position: {}".format(self, initial_focus))

        # Set up paths for temporary focus files, and plots if requested.
        image_dir = self.config['directories']['images']
        start_time = current_time(flatten=True)
        file_path = "{}/{}/{}/{}.{}".format(
            image_dir,
            'focus',
            self.uid,
            start_time,
            self.file_extension)

        if plots:
            # Take an image before focusing, grab a thumbnail from the centre and add it to the plot
            thumbnail = self._get_thumbnail(seconds, file_path, thumbnail_size)
            plt.subplot(3,1,1)
            plt.imshow(thumbnail, interpolation='none', cmap='cubehelix')
            plt.colorbar()
            plt.title('Initial focus position: {}'.format(initial_focus))

        # Set up encoder positions for autofocus sweep, truncating at focus travel limits if required.
        if coarse:
            focus_range = focus_range[1]
            focus_step = focus_step[1]
        else:
            focus_range = focus_range[0]
            focus_step = focus_step[0]
        
        focus_positions = np.arange(max(initial_focus - focus_range/2, self.focuser.min_position),
                                    min(initial_focus + focus_range/2, self.focuser.max_position) + 1,
                                    focus_step, dtype=np.int)
        n_positions = len(focus_positions)

        f4_y = np.empty((n_positions))
        f4_x = np.empty((n_positions))

        for i, position in enumerate(focus_positions):
            # Move focus, updating focus_positions with actual encoder position after move.
            focus_positions[i] = self.focuser.move_to(position)
            
            # Take exposure
            thumbnail = self._get_thumbnail(seconds, file_path, thumbnail_size)

            # Very simple background subtraction, uses sigma clipped median pixel value as background estimate
            thumbnail = thumbnail - sigma_clipped_stats(thumbnail)[1]

            # Calculate Vollath F4 focus metric for both y and x axes directions
            f4_y[i], f4_x[i] = images.vollath_F4(thumbnail)
            self.logger.debug("F4 at position {}: {}, {}".format(position, f4_y[i], f4_x[i]))

        # Find maximum values
        ymax = f4_y.argmax()
        xmax = f4_x.argmax()

        if ymax == 0 or ymax == (n_positions - 1) or xmax == 0 or xmax == (n_positions - 1):
            # TODO: have this automatically switch to coarse focus mode if this happens
            self.logger.warning("Best focus outside sweep range, aborting autofocus on {}!".format(self))
            final_focus = self.focuser.move_to(focus_positions[ymax])
            return initial_focus, final_focus

        if not coarse:
            # Fit to data around the max value to determine best focus position. Lorentz function seems to fit OK
            # provided you only fit in the immediate vicinity of the max value.

            # Initialise models
            fit_y = models.Lorentz1D(x_0=focus_positions[ymax], amplitude=f4_y.max())
            fit_x = models.Lorentz1D(x_0=focus_positions[xmax], amplitude=f4_x.max())

            # Initialise fitter
            fitter = fitting.LevMarLSQFitter()

            # Select data range for fitting. Tries to use 2 points either side of max, if in range.
            fitting_indices_y = (max(ymax - 2, 0), min(ymax + 2, n_positions - 1))
            fitting_indices_x = (max(xmax - 2, 0), min(xmax + 2, n_positions - 1))
            
            # Fit models to data
            fit_y = fitter(fit_y,
                           focus_positions[fitting_indices_y[0]:fitting_indices_y[1] + 1],
                           f4_y[fitting_indices_y[0]:fitting_indices_y[1] + 1])
            fit_x = fitter(fit_x,
                           focus_positions[fitting_indices_x[0]:fitting_indices_x[1] + 1],
                           f4_x[fitting_indices_x[0]:fitting_indices_x[1] + 1])

            best_y = fit_y.x_0.value
            best_x = fit_x.x_0.value

            best_focus = (best_y + best_x) / 2

        else:
            # Coarse focus, just use max value.
            best_focus = (focus_positions[ymax] + focus_positions[xmax]) / 2

        if plots:
            plt.subplot(3,1,2)
            plt.plot(focus_positions, f4_y, 'bo', label='$F_4$ $y$')
            plt.plot(focus_positions, f4_x, 'go', label='$F_4$ $x$')
            if not coarse:
                fys = np.arange(focus_positions[fitting_indices_y[0]], focus_positions[fitting_indices_y[1]] + 1)
                fxs = np.arange(focus_positions[fitting_indices_x[0]], focus_positions[fitting_indices_y[1]] + 1)
                plt.plot(fys, fit_y(fys), 'b-', label='$y$ fit')
                plt.plot(fxs, fit_x(fxs), 'g-', label='$x$ fit')

            plt.xlim(focus_positions[0] - focus_step/2, focus_positions[-1] + focus_step/2)
            plt.ylim(0, 1.1 * f4_y.max())  
            plt.vlines(initial_focus, 0, 1.1 * f4_y.max(), colors='k', linestyles=':', 
                       label='Initial focus')
            plt.vlines(best_focus, 0, 1.1 * f4_y.max(), colors='k', linestyles='--', 
                       label='Best focus')
            plt.xlabel('Focus position')
            plt.ylabel('Vollath $F_4$')
            if coarse:
                plt.title('Coarse autofocus of {} at {}'.format(self, start_time))
            else:
                plt.title('Fine autofocus of {} at {}'.format(self, start_time))
            plt.legend(loc='best')

        final_focus = self.focuser.move_to(best_focus)

        if plots:
            thumbnail = self._get_thumbnail(seconds, file_path, thumbnail_size)
            plt.subplot(3,1,3)
            plt.imshow(thumbnail, interpolation='none', cmap='cubehelix')
            plt.colorbar()
            plt.title('Final focus position: {}'.format(final_focus))
            plt.gcf().set_size_inches(7,18)
            plt.tight_layout()
            plt.show()
            plot_path = os.path.splitext(file_path)[0] + '.png'
            plt.savefig(plot_path)
            self.logger.info('Autofocus plot for camera {} written to {}'.format(self, plot_path))

        self.logger.debug('Autofocus of {} complete - final focus position: {}'.format(self, final_focus))
        return initial_focus, final_focus

    def _get_thumbnail(self, seconds, file_path, thumbnail_size):
        """
        Takes an image, grabs the data, deletes the FITS file and 
        returns a thumbnail from the centre of the iamge.
        """
        self.take_exposure(seconds, filename=file_path, blocking=True)
        image = fits.getdata(file_path)
        os.unlink(file_path)
        thumbnail = images.crop_data(image, box_width=thumbnail_size)
        return thumbnail
    
    def __str__(self):
        try:
            return "{} ({}) on {} with {} focuser".format(self.name, self.uid, self.port, self.focuser.name)
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
