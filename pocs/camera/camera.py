import copy
import os
import re
import shutil
import subprocess
import threading
import yaml
from contextlib import suppress

from astropy.io import fits
from astropy.time import Time
import astropy.units as u

from pocs.base import PanBase
from pocs.utils import current_time
from pocs.utils import error
from pocs.utils import listify
from pocs.utils import load_module
from pocs.utils import images as img_utils
from pocs.utils import get_quantity_value
from pocs.utils.images import fits as fits_utils
from pocs.focuser import AbstractFocuser
from pocs.filterwheel import AbstractFilterWheel


class AbstractCamera(PanBase):

    """Base class for all cameras.

    Attributes:
        filter_type (str): Type of filter attached to camera, default RGGB.
        focuser (`pocs.focuser.*.Focuser`|None): Focuser for the camera, default None.
        filter_wheel (`pocs.filterwheel.*.FilterWheel`|None): Filter wheel for the camera, default
            None.
        is_primary (bool): If this camera is the primary camera for the system, default False.
        model (str): The model of camera, such as 'gphoto2', 'sbig', etc. Default 'simulator'.
        name (str): Name of the camera, default 'Generic Camera'.
        port (str): The port the camera is connected to, typically a usb device, default None.
        set_point (astropy.units.Quantity): image sensor cooling target temperature.
        gain (int): The gain setting of the camera (ZWO cameras only).
        image_type (str): Image format of the camera, e.g. 'RAW16', 'RGB24' (ZWO cameras only).
        timeout (astropy.units.Quantity): max time to wait after exposure before TimeoutError.
        readout_time (float): approximate time to readout the camera after an exposure.
        file_extension (str): file extension used by the camera's image data, e.g. 'fits'
        library_path (str): path to camera library, e.g. '/usr/local/lib/libfli.so' (SBIG, FLI, ZWO)
        properties (dict): A collection of camera properties as read from the camera.

    Notes:
        The port parameter is not used by SBIG or ZWO cameras, and is deprecated for FLI cameras.
        For these cameras serial_number should be passed to the constructor instead. For SBIG and
        FLI this should simply be the serial number engraved on the camera case, whereas for
        ZWO cameras this should be the 8 character ID string previously saved to the camera
        firmware.  This can be done using ASICAP, or `pocs.camera.libasi.ASIDriver.set_ID()`.
    """

    def __init__(self,
                 name='Generic Camera',
                 model='simulator',
                 port=None,
                 primary=False,
                 focuser=None,
                 filterwheel=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = model
        self.port = port
        self.name = name
        self.is_primary = primary

        self._filter_type = kwargs.get('filter_type', 'RGGB')

        self._connected = False
        self._serial_number = kwargs.get('serial_number', 'XXXXXX')
        self._readout_time = kwargs.get('readout_time', 5.0)
        self._file_extension = kwargs.get('file_extension', 'fits')
        self._current_observation = None

        self._create_subcomponent(subcomponent=focuser,
                                  sub_name='focuser',
                                  class_name='Focuser',
                                  base_class=AbstractFocuser)
        self._create_subcomponent(subcomponent=filterwheel,
                                  sub_name='filterwheel',
                                  class_name='FilterWheel',
                                  base_class=AbstractFilterWheel)

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
    def ccd_temp(self):
        """
        Get current temperature of the camera's image sensor.

        Note: this only needs to be implemented for cameras which can provided this information,
        e.g. those with cooled image sensors.
        """
        raise NotImplementedError

    @property
    def ccd_set_point(self):
        """
        Get current value of the CCD set point, the target temperature for the camera's
        image sensor cooling control.

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError

    @ccd_set_point.setter
    def ccd_set_point(self, set_point):
        """
        Set value of the CCD set point, the target temperature for the camera's image sensor
        cooling control.

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError

    @property
    def ccd_cooling_enabled(self):
        """
        Get current status of the camera's image sensor cooling system (enabled/disabled).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        return False

    @ccd_cooling_enabled.setter
    def ccd_cooling_enabled(self, enabled):
        """
        Set status of the camera's image sensor cooling system (enabled/disabled).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        and allow cooling to be enabled/disabled (e.g. SBIG cameras).
        """
        raise NotImplementedError

    @property
    def ccd_cooling_power(self):
        """
        Get current power level of the camera's image sensor cooling system (typically as
        a percentage of the maximum).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError

    @property
    def filter_type(self):
        """ Image sensor filter type (e.g. 'RGGB') or name of the current filter (e.g. 'g2_3') """
        if self.filterwheel:
            return self.filterwheel.current_filter
        else:
            return self._filter_type

    @property
    def is_exposing(self):
        """ True if an exposure is currently under way, otherwise False """
        raise NotImplementedError

##################################################################################################
# Methods
##################################################################################################

    def take_observation(self, observation, headers=None, filename=None, **kwargs):
        """Take an observation

        Gathers various header information, sets the file path, and calls
            `take_exposure`. Also creates a `threading.Event` object and a
            `threading.Thread` object. The Thread calls `process_exposure`
            after the exposure had completed and the Event is set once
            `process_exposure` finishes.

        Args:
            observation (~pocs.scheduler.observation.Observation): Object
                describing the observation
            headers (dict, optional): Header data to be saved along with the file.
            filename (str, optional): pass a filename for the output FITS file to
                overrride the default file naming system
            **kwargs (dict): Optional keyword arguments (`exp_time`, dark)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        observation_event = threading.Event()

        exp_time, file_path, image_id, metadata = self._setup_observation(observation,
                                                                          headers,
                                                                          filename,
                                                                          **kwargs)

        exposure_event = self.take_exposure(seconds=exp_time, filename=file_path, **kwargs)

        # Add most recent exposure to list
        if self.is_primary:
            if 'POINTING' in headers:
                observation.pointing_images[image_id] = file_path
            else:
                observation.exposure_list[image_id] = file_path

        # Process the exposure once readout is complete
        t = threading.Thread(
            target=self.process_exposure,
            args=(metadata, observation_event, exposure_event),
            daemon=True)
        t.name = '{}Thread'.format(self.name)
        t.start()

        return observation_event

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      *args,
                      **kwargs):
        """Take an exposure for given number of seconds and saves to provided filename.

        Args:
            seconds (u.second, optional): Length of exposure.
            filename (str, optional): Image is saved to this filename.
            dark (bool, optional): Exposure is a dark frame, default False. On cameras that support
                taking dark frames internally (by not opening a mechanical shutter) this will be
                done, for other cameras the light must be blocked by some other means. In either
                case setting dark to True will cause the `IMAGETYP` FITS header keyword to have
                value 'Dark Frame' instead of 'Light Frame'. Set dark to None to disable the
                `IMAGETYP` keyword entirely.
            blocking (bool, optional): If False (default) returns immediately after starting
                the exposure, if True will block until it completes.

        Returns:
            threading.Event: Event that will be set when exposure is complete.

        """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.error("Must pass filename for take_exposure")

        if self.filterwheel and self.filterwheel.is_moving:
            msg = "Attempt to start exposure on {} while filterwheel is moving, ignoring.".format(
                self)
            raise error.PanError(msg)

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

        self.logger.debug('Taking {} second exposure on {}: {}'.format(
            seconds, self.name, filename))

        exposure_event = threading.Event()
        header = self._fits_header(seconds, dark)

        self._take_exposure(seconds=seconds,
                            filename=filename,
                            dark=dark,
                            exposure_event=exposure_event,
                            header=header,
                            *args, **kwargs)

        if blocking:
            exposure_event.wait()

        return exposure_event

    def process_exposure(self, info, observation_event, exposure_event=None):
        """
        Processes the exposure.

        If the camera is a primary camera, extract the jpeg image and save metadata to mongo
        `current` collection. Saves metadata to mongo `observations` collection for all images.

        Args:
            info (dict): Header metadata saved for the image
            observation_event (threading.Event): An event that is set signifying that the
                camera is done with this exposure
            exposure_event (threading.Event, optional): An event that should be set
                when the exposure is complete, triggering the processing.
        """
        # If passed an Event that signals the end of the exposure wait for it to be set
        if exposure_event is not None:
            exposure_event.wait()

        image_id = info['image_id']
        seq_id = info['sequence_id']
        file_path = info['file_path']
        exptime = info['exp_time']
        field_name = info['field_name']

        image_title = '{} [{}s] {} {}'.format(field_name,
                                              exptime,
                                              seq_id.replace('_', ' '),
                                              current_time(pretty=True))

        try:
            self.logger.debug("Processing {}".format(image_title))
            img_utils.make_pretty_image(file_path,
                                        title=image_title,
                                        link_latest=info['is_primary'])
        except Exception as e:  # pragma: no cover
            self.logger.warning('Problem with extracting pretty image: {}'.format(e))

        file_path = self._process_fits(file_path, info)
        self.logger.debug("Finished processing FITS.")
        with suppress(Exception):
            info['exp_time'] = info['exp_time'].value

        if info['is_primary']:
            self.logger.debug("Adding current observation to db: {}".format(image_id))
            try:
                self.db.insert_current('observations', info, store_permanently=False)
            except Exception as e:
                self.logger.error('Problem adding observation to db: {}'.format(e))
        else:
            self.logger.debug('Compressing {}'.format(file_path))
            fits_utils.fpack(file_path)

        self.logger.debug("Adding image metadata to db: {}".format(image_id))

        self.db.insert('observations', {
            'data': info,
            'date': current_time(datetime=True),
            'sequence_id': seq_id,
        })

        # Mark the event as done
        observation_event.set()

    def autofocus(self,
                  seconds=None,
                  focus_range=None,
                  focus_step=None,
                  thumbnail_size=None,
                  keep_files=None,
                  take_dark=None,
                  merit_function='vollath_F4',
                  merit_function_kwargs={},
                  mask_dilations=None,
                  coarse=False,
                  make_plots=False,
                  blocking=False,
                  *args, **kwargs):
        """
        Focuses the camera using the specified merit function. Optionally performs
        a coarse focus to find the approximate position of infinity focus, which
        should be followed by a fine focus before observing.

        Args:
            seconds (scalar, optional): Exposure time for focus exposures, if not
                specified will use value from config.
            focus_range (2-tuple, optional): Coarse & fine focus sweep range, in
                encoder units. Specify to override values from config.
            focus_step (2-tuple, optional): Coarse & fine focus sweep steps, in
                encoder units. Specify to override values from config.
            thumbnail_size (int, optional): Size of square central region of image
                to use, default 500 x 500 pixels.
            keep_files (bool, optional): If True will keep all images taken
                during focusing. If False (default) will delete all except the
                first and last images from each focus run.
            take_dark (bool, optional): If True will attempt to take a dark frame
                before the focus run, and use it for dark subtraction and hot
                pixel masking, default True.
            merit_function (str/callable, optional): Merit function to use as a
                focus metric, default vollath_F4.
            merit_function_kwargs (dict, optional): Dictionary of additional
                keyword arguments for the merit function.
            mask_dilations (int, optional): Number of iterations of dilation to perform on the
                saturated pixel mask (determine size of masked regions), default 10
            coarse (bool, optional): Whether to perform a coarse focus, otherwise will perform
                a fine focus. Default False.
            make_plots (bool, optional: Whether to write focus plots to images folder, default
                False.
            blocking (bool, optional): Whether to block until autofocus complete, default False.

        Returns:
            threading.Event: Event that will be set when autofocusing is complete

        Raises:
            ValueError: If invalid values are passed for any of the focus parameters.
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
                                      mask_dilations=mask_dilations,
                                      coarse=coarse,
                                      make_plots=make_plots,
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
        thumbnail = img_utils.crop_data(image, box_width=thumbnail_size)
        return thumbnail

    def _take_exposure(self, *args, **kwargs):
        raise NotImplementedError

    def _fits_header(self, seconds, dark=None):
        header = fits.Header()
        header.set('INSTRUME', self.uid, 'Camera serial number')
        now = Time.now()
        header.set('DATE-OBS', now.fits, 'Start of exposure')
        header.set('EXPTIME', get_quantity_value(seconds, u.second), 'Seconds')
        if dark is not None:
            if dark:
                header.set('IMAGETYP', 'Dark Frame')
            else:
                header.set('IMAGETYP', 'Light Frame')
        header.set('FILTER', self.filter_type)
        with suppress(NotImplementedError):
            header.set('CCD-TEMP', get_quantity_value(self.ccd_temp, u.Celsius), 'Degrees C')
        with suppress(NotImplementedError):
            header.set('SET-TEMP', get_quantity_value(self.ccd_set_point, u.Celsius), 'Degrees C')
        with suppress(NotImplementedError):
            header.set('COOL-POW', get_quantity_value(self.ccd_cooling_power, u.percent),
                       'Percentage')
        header.set('CAM-ID', self.uid, 'Camera serial number')
        header.set('CAM-NAME', self.name, 'Camera name')
        header.set('CAM-MOD', self.model, 'Camera model')

        if self.focuser:
            header = self.focuser._add_fits_keywords(header)
        if self.filterwheel:
            header = self.filterwheel._add_fits_keywords(header)

        return header

    def _setup_observation(self, observation, headers, filename, **kwargs):
        if headers is None:
            headers = {}

        start_time = headers.get('start_time', current_time(flatten=True))

        if not observation.seq_time:
            observation.seq_time = start_time

        # Get the filename
        image_dir = os.path.join(
            observation.directory,
            self.uid,
            observation.seq_time
        )

        # Get full file path
        if filename is None:
            file_path = os.path.join(
                image_dir,
                '{}.{}'.format(start_time, self.file_extension)
            )

        else:
            # Add extension
            if '.' not in filename:
                filename = '{}.{}'.format(filename, self.file_extension)

            # Add directory
            if '/' not in filename:
                filename = os.path.join(image_dir, filename)

            file_path = filename

        unit_id = self.config['pan_id']

        # Make the image_id
        image_id = '{}_{}_{}'.format(
            unit_id,
            self.uid,
            start_time
        )
        self.logger.debug("image_id: {}".format(image_id))

        # Make the sequence_id
        sequence_id = '{}_{}_{}'.format(
            unit_id,
            self.uid,
            observation.seq_time
        )

        # Camera metadata
        metadata = {
            'camera_name': self.name,
            'camera_uid': self.uid,
            'field_name': observation.field.field_name,
            'file_path': file_path,
            'filter': self.filter_type,
            'image_id': image_id,
            'is_primary': self.is_primary,
            'sequence_id': sequence_id,
            'start_time': start_time,
        }
        metadata.update(headers)

        exp_time = kwargs.get('exp_time', observation.exp_time.value)
        # The exp_time header data is set as part of observation but can
        # be override by passed parameter so update here.
        metadata['exp_time'] = exp_time

        return exp_time, file_path, image_id, metadata

    def _process_fits(self, file_path, info):
        """
        Add FITS headers from info the same as images.cr2_to_fits()
        """
        self.logger.debug("Updating FITS headers: {}".format(file_path))
        fits_utils.update_headers(file_path, info)
        return file_path

    def _create_subcomponent(self, subcomponent, sub_name, class_name, base_class):
        """
        Creates a subcomponent as an attribute of the camera. Can do this from either an instance
        of the appropriate subcomponent class, or from a dictionary of keyword arguments for the
        subcomponent class' constructor.

        Args:
            subcomponent (instance of class_name | dict): the subcomponent object, or the keyword
                arguments required to create it.
            sub_name (str): name of the subcomponent, e.g. 'focuser'. Will be used as the attribute
                name, and must also match the name corresponding POCS submodule for this
                subcomponent, e.g. `pocs.focuser`
            class_name (str): name of the subcomponent class, e.g. 'Focuser'
            base_class (class): the base class for the subcomponent, e.g.
                `pocs.focuser.AbtractFocuser`, used to check whether subcomponent is an instance.
        """
        if subcomponent:
            if isinstance(subcomponent, base_class):
                self.logger.debug("{} received: {}".format(class_name, subcomponent))
                setattr(self, sub_name, subcomponent)
                getattr(self, sub_name).camera = self
            elif isinstance(subcomponent, dict):
                module_name = 'pocs.{}.{}'.format(sub_name, subcomponent['model'])
                try:
                    module = load_module(module_name)
                except AttributeError as err:
                    self.logger.critical("Couldn't import {} module {}!".format(
                        class_name, module_name))
                    raise err
                else:
                    subcomponent_kwargs = copy.copy(subcomponent)
                    subcomponent_kwargs.update({'camera': self, 'config': self.config})
                    setattr(self, sub_name, getattr(module, class_name)(**subcomponent_kwargs))
            else:
                # Should have been passed either an instance of base_class or dict with subcomponent
                # configuration. Got something else...
                self.logger.error("Expected either a {} instance or dict, got {}".format(
                    class_name, subcomponent))
                setattr(self, sub_name, None)
        else:
            setattr(self, sub_name, None)

    def __str__(self):
        name = self.name
        if self.is_primary:
            name += ' [Primary]'

        s = "{} ({}) on {}".format(name, self.uid, self.port)

        if self.focuser:
            s += ' with {}'.format(self.focuser.name)
            if self.filterwheel:
                s += ' & {}'.format(self.filterwheel.name)
        elif self.filterwheel:
            s += ' with {}'.format(self.filterwheel.name)

        return s


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
