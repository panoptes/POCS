import copy
import os
import re
import shutil
import subprocess
import threading
import time
from contextlib import suppress
from abc import ABCMeta, abstractmethod

from astropy.io import fits
from astropy.time import Time
import astropy.units as u

from panoptes.utils import current_time
from panoptes.utils import error
from panoptes.utils import listify
from panoptes.utils import images as img_utils
from panoptes.utils import get_quantity_value
from panoptes.utils import CountdownTimer
from panoptes.utils.images import fits as fits_utils
from panoptes.utils.library import load_module

from panoptes.pocs.base import PanBase
from panoptes.utils.serializers import from_yaml


def parse_config(lines):
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


class AbstractCamera(PanBase, metaclass=ABCMeta):
    """Base class for all cameras.

    Attributes:
        filter_type (str): Type of filter attached to camera, default RGGB.
        focuser (`panoptes.pocs.focuser.AbstractFocuser`|None): Focuser for the camera, default None.
        filter_wheel (`panoptes.pocs.filterwheel.AbstractFilterWheel`|None): Filter wheel for the camera,
            default None.
        is_primary (bool): If this camera is the primary camera for the system, default False.
        model (str): The model of camera, such as 'gphoto2', 'sbig', etc. Default 'simulator'.
        name (str): Name of the camera, default 'Generic Camera'.
        port (str): The port the camera is connected to, typically a usb device, default None.
        target_temperature (astropy.units.Quantity): image sensor cooling target temperature.
        temperature_tolerance (astropy.units.Quantity): tolerance for image sensor temperature.
        gain (int): The gain setting of the camera (ZWO cameras only).
        image_type (str): Image format of the camera, e.g. 'RAW16', 'RGB24' (ZWO cameras only).
        timeout (astropy.units.Quantity): max time to wait after exposure before TimeoutError.
        readout_time (float): approximate time to readout the camera after an exposure.
        file_extension (str): file extension used by the camera's image data, e.g. 'fits'
        library_path (str): path to camera library, e.g. '/usr/local/lib/libfli.so' (SBIG, FLI, ZWO)
        properties (dict): A collection of camera properties as read from the camera.
        is_cooled_camera (bool): True if camera has image sensor cooling capability.
        is_temperature_stable (bool): True if image sensor temperature is stable.
        is_exposing (bool): True if an exposure is currently under way, otherwise False.

    Notes:
        The port parameter is not used by SBIG or ZWO cameras, and is deprecated for FLI cameras.
        For these cameras serial_number should be passed to the constructor instead. For SBIG and
        FLI this should simply be the serial number engraved on the camera case, whereas for
        ZWO cameras this should be the 8 character ID string previously saved to the camera
        firmware.  This can be done using ASICAP, or `panoptes.pocs.camera.libasi.ASIDriver.set_ID()`.
    """

    _subcomponent_classes = {'Focuser', 'FilterWheel'}
    _subcomponent_names = {sub_class.casefold() for sub_class in _subcomponent_classes}

    def __init__(self,
                 name='Generic Camera',
                 model='simulator',
                 port=None,
                 primary=False,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = model
        self.port = port
        self.name = name
        self.is_primary = primary

        self._filter_type = kwargs.get('filter_type', 'RGGB')
        self._serial_number = kwargs.get('serial_number', 'XXXXXX')
        self._readout_time = get_quantity_value(kwargs.get('readout_time', 5.0), unit=u.second)
        self._file_extension = kwargs.get('file_extension', 'fits')
        self._timeout = get_quantity_value(kwargs.get('timeout', 10), unit=u.second)
        # Default is uncooled camera. Should be set to True if appropriate in camera connect()
        # method, based on info received from camera.
        self._is_cooled_camera = False
        self.temperature_tolerance = kwargs.get('temperature_tolerance', 0.5 * u.Celsius)

        self._connected = False
        self._current_observation = None
        self._exposure_event = threading.Event()
        self._exposure_event.set()
        self._is_exposing = False

        for subcomponent_class in self._subcomponent_classes:
            self._create_subcomponent(subcomponent=kwargs.get(subcomponent_class.casefold()),
                                      class_name=subcomponent_class)

        self.logger.debug(f'Camera created: {self}')

    ##################################################################################################
    # Properties
    ##################################################################################################

    @property
    def uid(self):
        """Return unique identifier for camera. """
        return self._serial_number

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
    def egain(self):
        """Image sensor gain in e-/ADU as reported by the camera."""
        raise NotImplementedError  # pragma: no cover

    @property
    def bit_depth(self):
        """ADC bit depth."""
        raise NotImplementedError  # pragma: no cover

    @property
    def temperature(self):
        """
        Get current temperature of the camera's image sensor.

        Note: this only needs to be implemented for cameras which can provided this information,
        e.g. those with cooled image sensors.
        """
        raise NotImplementedError  # pragma: no cover

    @property
    def target_temperature(self):
        """
        Get current value of the target temperature for the camera's image sensor cooling control.

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError  # pragma: no cover

    @target_temperature.setter
    def target_temperature(self, target_temperature):
        """
        Set value of the CCD set point, the target temperature for the camera's image sensor
        cooling control.

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError  # pragma: no cover

    @property
    def temperature_tolerance(self):
        """
        Get current value of the image sensor temperature tolerance.

        If the image sensor temperature differs from the target temperature by more than the
        temperature tolerance then the temperature is not considered stable (by
        is_temperature_stable) and, for cooled cameras, is_ready will report False.
        """
        return self._temperature_tolerance

    @temperature_tolerance.setter
    def temperature_tolerance(self, temperature_tolerance):
        """ Set the value of the image sensor temperature tolerance. """
        if not isinstance(temperature_tolerance, u.Quantity):
            temperature_tolerance = temperature_tolerance * u.Celsius
        self._temperature_tolerance = temperature_tolerance

    @property
    def cooling_enabled(self):
        """
        Get current status of the camera's image sensor cooling system (enabled/disabled).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        return False

    @cooling_enabled.setter
    def cooling_enabled(self, enable):
        """
        Set status of the camera's image sensor cooling system (enabled/disabled).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        and allow cooling to be enabled/disabled (e.g. SBIG cameras).
        """
        raise NotImplementedError  # pragma: no cover

    @property
    def cooling_power(self):
        """
        Get current power level of the camera's image sensor cooling system (typically as
        a percentage of the maximum).

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        raise NotImplementedError  # pragma: no cover

    @property
    def filter_type(self):
        """ Image sensor filter type (e.g. 'RGGB') or name of the current filter (e.g. 'g2_3') """
        if self.filterwheel:
            return self.filterwheel.current_filter
        else:
            return self._filter_type

    @property
    def is_cooled_camera(self):
        """ True if camera has image sensor cooling capability """
        return self._is_cooled_camera

    @property
    def is_temperature_stable(self):
        """ True if image sensor temperature is stable, False if not.

        See also: See `temperature_tolerance` for more information about the temperature stability.
        An uncooled camera, or cooled camera with cooling disabled, will always return False.
        """
        if self.is_cooled_camera and self.cooling_enabled:
            at_target = abs(self.temperature - self.target_temperature) \
                        < self.temperature_tolerance
            if not at_target or self.cooling_power == 100 * u.percent:
                self.logger.warning(f'Unstable CCD temperature in {self}.')
                self.logger.warning(f'Cooling={self.cooling_power:.02f} '
                                    f'Temp={self.temperature:.02f} '
                                    f'Target={self.target_temperature:.02f} '
                                    f'Tolerance={self.temperature_tolerance:.02f}')
                return False
            else:
                return True
        else:
            return False

    @property
    def is_exposing(self):
        """ True if an exposure is currently under way, otherwise False. """
        return self._is_exposing

    @property
    def readiness(self):
        """ Dictionary detailing the readiness of the camera system to take an exposure. """
        current_readiness = {}
        # For cooled camera expect stable temperature before taking exposure
        if self.is_cooled_camera:
            current_readiness['temperature_stable'] = self.is_temperature_stable
        # Check all the subcomponents too, e.g. make sure filterwheel/focuser aren't moving.
        for sub_name in self._subcomponent_names:
            if getattr(self, sub_name):
                current_readiness['sub_name'] = getattr(self, sub_name).is_ready

        # Make sure there isn't an exposure already in progress.
        current_readiness['not_exposing'] = not self.is_exposing

        return current_readiness

    @property
    def is_ready(self):
        """ True if camera is ready to start another exposure, otherwise False. """
        current_readiness = self.readiness

        # For cooled camera expect stable temperature before taking exposure
        if not current_readiness.get('temperature_stable', True):
            self.logger.warning(f"Camera {self} not ready: unstable temperature.")

        # Check all the subcomponents too, e.g. make sure filterwheel/focuser aren't moving.
        for sub_name in self._subcomponent_names:
            if not current_readiness.get(sub_name, True):
                self.logger.warning(f"Camera {self} not ready: {sub_name} not ready.")

        # Make sure there isn't an exposure already in progress.
        if not current_readiness['not_exposing']:
            self.logger.warning(f"Camera {self} not ready: exposure already in progress.")

        return all(current_readiness.values())

    ##################################################################################################
    # Methods
    ##################################################################################################

    @abstractmethod
    def connect(self):
        raise NotImplementedError  # pragma: no cover

    def take_observation(self, observation, headers=None, filename=None, **kwargs):
        """Take an observation

        Gathers various header information, sets the file path, and calls
            `take_exposure`. Also creates a `threading.Event` object and a
            `threading.Thread` object. The Thread calls `process_exposure`
            after the exposure had completed and the Event is set once
            `process_exposure` finishes.

        Args:
            observation (~panoptes.pocs.scheduler.observation.Observation): Object
                describing the observation
            headers (dict, optional): Header data to be saved along with the file.
            filename (str, optional): pass a filename for the output FITS file to
                overrride the default file naming system
            **kwargs (dict): Optional keyword arguments (`exptime`, dark)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        observation_event = threading.Event()

        # Setup the observation
        exptime, file_path, image_id, metadata = self._setup_observation(observation,
                                                                         headers,
                                                                         filename,
                                                                         **kwargs)

        # pop exptime from kwarg as its now in exptime
        exptime = kwargs.pop('exptime', observation.exptime.value)

        # start the exposure
        exposure_event = self.take_exposure(seconds=exptime, filename=file_path, **kwargs)

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
        t.name = f'{self.name}Thread'
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

        # Check that the camera (and subcomponents) is ready
        if not self.is_ready:
            # Work out why the camera isn't ready.
            current_readiness = self.readiness
            problems = []
            if not current_readiness.get('temperature_stable', True):
                problems.append("unstable temperature")

            for sub_name in self._subcomponent_names:
                if not current_readiness.get(sub_name, True):
                    problems.append(f"{sub_name} not ready")

            if not current_readiness['not_exposing']:
                problems.append("exposure in progress")

            problems_string = ", ".join(problems)
            msg = f"Attempt to start exposure on {self} while not ready: {problems_string}."
            raise error.PanError(msg)

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

        self.logger.debug(f'Taking {seconds} exposure on {self.name}: {filename}')

        header = self._create_fits_header(seconds, dark)

        if not self._exposure_event.is_set():
            msg = f"Attempt to take exposure on {self} while one already in progress."
            raise error.PanError(msg)

        # Clear event now to prevent any other exposures starting before this one is finished.
        self._exposure_event.clear()

        try:
            # Camera type specific exposure set up and start
            readout_args = self._start_exposure(seconds, filename, dark, header, *args, *kwargs)
        except (RuntimeError, ValueError, error.PanError) as err:
            self._exposure_event.set()
            raise error.PanError("Error starting exposure on {}: {}".format(self, err))

        # Start polling thread that will call camera type specific _readout method when done
        readout_thread = threading.Timer(interval=get_quantity_value(seconds, unit=u.second),
                                         function=self._poll_exposure,
                                         args=(readout_args,))
        readout_thread.start()

        if blocking:
            self.logger.debug("Blocking on exposure event for {}".format(self))
            self._exposure_event.wait()

        return self._exposure_event

    def process_exposure(self, info, observation_event, exposure_event=None):
        """
        Processes the exposure.

        If the camera is a primary camera, extract the jpeg image and save metadata to database
        `current` collection. Saves metadata to `observations` collection for all images.

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
        exptime = info['exptime']
        field_name = info['field_name']

        image_title = '{} [{}s] {} {}'.format(field_name,
                                              exptime,
                                              seq_id.replace('_', ' '),
                                              current_time(pretty=True))

        try:
            self.logger.debug("Making pretty image for {}".format(file_path))
            link_path = None
            if info['is_primary']:
                # This should be in the config somewhere.
                link_path = os.path.expandvars('$PANDIR/images/latest.jpg')

            img_utils.make_pretty_image(file_path,
                                        title=image_title,
                                        link_path=link_path)
        except Exception as e:  # pragma: no cover
            self.logger.warning('Problem with extracting pretty image: {}'.format(e))

        self.logger.debug(f'Starting FITS processing for {file_path}')
        file_path = self._process_fits(file_path, info)
        self.logger.debug(f'Finished FITS processing for {file_path}')
        with suppress(Exception):
            info['exptime'] = info['exptime'].value

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
        thumbnail = None
        try:
            thumbnail = img_utils.crop_data(image, box_width=thumbnail_size)
        except Exception as e:
            self.logger.warning(f'Problem getting thumbnail: {e!r}')
        return thumbnail

    @abstractmethod
    def _start_exposure(self, seconds=None, filename=None, dark=False, header=None, *args, **kwargs):
        """Responsible for the camera-specific process that start an exposure.

        This method is called from the `take_exposure` method and is used to handle
        hardware-specific items for each camera.

        Note:
            Each sub-class is required to implement this abstract method. The derived
            method should at a minimum implement the described parameters.

        Args:
            seconds (float): The number of seconds to expose for.
            filename (str): Filename location for saved image.
            dark (bool): If image is a dark frame.
            header (dict): Optional headers to save with the image.

        Returns:
            tuple|list: Any arguments required by the camera-specific `_readout`
                method, which should be implemented at the same time as this method.
        """
        pass  # pragma: no cover

    @abstractmethod
    def _readout(self, filename=None, **kwargs):
        """Performs the camera-specific readout after exposure.

        This method is called from the `_poll_exposure` private method and is responsible
        for the camera-specific readout commands. This method is responsible for actually
        writing the FITS file.

        Note:
            Each sub-class is required to implement this abstract method. The derived
            method should at a minimum implement the described parameters.

        """
        pass  # pragma: no cover

    def _poll_exposure(self, readout_args):
        timer = CountdownTimer(duration=self._timeout)
        try:
            while self.is_exposing:
                if timer.expired():
                    msg = f"Timeout waiting for exposure on {self} to complete"
                    raise error.Timeout(msg)
                time.sleep(0.01)
        except (RuntimeError, error.PanError) as err:
            # Error returned by driver at some point while polling
            self.logger.error(f'Error while waiting for exposure on {self}: {err!r}')
            raise err
        else:
            # Camera type specific readout function
            self._readout(*readout_args)
        finally:
            self._exposure_event.set()  # Make sure this gets set regardless of readout errors

    def _create_fits_header(self, seconds, dark=None):
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
        with suppress(NotImplementedError):  # SBIG & ZWO cameras report their gain.
            header.set('EGAIN', get_quantity_value(self.egain, u.electron / u.adu),
                       'Electrons/ADU')
        with suppress(NotImplementedError):
            # ZWO cameras have ADC bit depths with differ from BITPIX
            header.set('BITDEPTH', int(get_quantity_value(self.bit_depth, u.bit)), 'ADC bit depth')
        with suppress(NotImplementedError):
            # Some non cooled cameras can still report the image sensor temperature
            header.set('CCD-TEMP', get_quantity_value(self.temperature, u.Celsius), 'Degrees C')
        if self.is_cooled_camera:
            header.set('SET-TEMP', get_quantity_value(self.target_temperature, u.Celsius),
                       'Degrees C')
            header.set('COOL-POW', get_quantity_value(self.cooling_power, u.percent),
                       'Percentage')
        header.set('CAM-ID', self.uid, 'Camera serial number')
        header.set('CAM-NAME', self.name, 'Camera name')
        header.set('CAM-MOD', self.model, 'Camera model')

        for sub_name in self._subcomponent_names:
            subcomponent = getattr(self, sub_name)
            if subcomponent:
                header = subcomponent._add_fits_keywords(header)

        return header

    def _setup_observation(self, observation, headers, filename, **kwargs):
        headers = headers or None

        # Move the filterwheel if necessary
        if self.filterwheel is not None:
            if observation.filter_name is not None:
                try:
                    # Move the filterwheel
                    self.logger.debug(f'Moving filterwheel={self.filterwheel} to filter_name={observation.filter_name}')
                    self.filterwheel.move_to(observation.filter_name, blocking=True)
                except Exception as e:
                    self.logger.error(f'Error moving filterwheel on {self} to'
                                      f' {observation.filter_name}: {e!r}')
                    raise (e)

            else:
                self.logger.info(f'Filter {observation.filter_name} requested by'
                                 f' observation but {self.filterwheel} is missing that filter, using'
                                 f' {self.filter_type}.')

        if headers is None:
            start_time = current_time(flatten=True)
        else:
            start_time = headers.get('start_time', current_time(flatten=True))

        if not observation.seq_time:
            self.logger.debug(f'Setting observation seq_time={start_time}')
            observation.seq_time = start_time

        # Get the filename
        self.logger.debug(f'Setting image_dir={observation.directory}/{self.uid}/{observation.seq_time}')
        image_dir = os.path.join(
            observation.directory,
            self.uid,
            observation.seq_time
        )

        # Get full file path
        if filename is None:
            file_path = os.path.join(image_dir, f'{start_time}.{self.file_extension}')
        else:
            # Add extension
            if '.' not in filename:
                filename = f'{filename}.{self.file_extension}'

            # Add directory
            if '/' not in filename:
                filename = os.path.join(image_dir, filename)

            file_path = filename

        self.logger.debug(f'Setting file_path={file_path}')

        unit_id = self.get_config('pan_id')

        # Make the IDs.
        sequence_id = f'{unit_id}_{self.uid}_{observation.seq_time}'
        image_id = f'{unit_id}_{self.uid}_{start_time}'

        self.logger.debug(f"sequence_id={sequence_id} image_id={image_id}")

        # Make the sequence_id

        # The exptime header data is set as part of observation but can
        # be override by passed parameter so update here.
        exptime = kwargs.get('exptime', observation.exptime.value)

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
            'exptime': exptime
        }
        if observation.filter_name is not None:
            metadata['filter_request'] = observation.filter_name

        if headers is not None:
            metadata.update(headers)

        self.logger.debug(
            f'Observation setup: exptime={exptime} file_path={file_path} image_id={image_id} metadata={metadata}')
        return exptime, file_path, image_id, metadata

    def _process_fits(self, file_path, info):
        """
        Add FITS headers from info the same as images.cr2_to_fits()
        """
        self.logger.debug(f"Updating FITS headers: {file_path}")
        fits_utils.update_observation_headers(file_path, info)
        self.logger.debug(f"Finished FITS headers: {file_path}")

        return file_path

    def _create_subcomponent(self, subcomponent, class_name):
        """
        Creates a subcomponent as an attribute of the camera. Can do this from either an instance
        of the appropriate subcomponent class, or from a dictionary of keyword arguments for the
        subcomponent class' constructor.

        Args:
            subcomponent (instance of sub_name | dict): the subcomponent object, or the keyword
                arguments required to create it.
            class_name (str): name of the subcomponent class, e.g. 'Focuser'. Lower cased version
                will be used as the attribute name, and must also match the name of the
                corresponding POCS submodule for this subcomponent, e.g. `panoptes.pocs.focuser`.
        """
        class_name_lower = class_name.casefold()
        if subcomponent:
            base_module_name = "panoptes.pocs.{0}.{0}".format(class_name_lower)
            try:
                base_module = load_module(base_module_name)
            except error.NotFound as err:
                self.logger.critical(f"Couldn't import {class_name} base class module {base_module_name}!")
                raise err
            base_class = getattr(base_module, f"Abstract{class_name}")

            if isinstance(subcomponent, base_class):
                self.logger.debug(f"{class_name} received: {subcomponent}")
                setattr(self, class_name_lower, subcomponent)
                getattr(self, class_name_lower).camera = self
            elif isinstance(subcomponent, dict):
                module_name = 'panoptes.pocs.{}.{}'.format(class_name_lower, subcomponent['model'])
                try:
                    module = load_module(module_name)
                except error.NotFound as err:
                    self.logger.critical(f"Couldn't import {class_name} module {module_name}!")
                    raise err
                subcomponent_kwargs = copy.deepcopy(subcomponent)
                subcomponent_kwargs.update({'camera': self, 'config_port': self._config_port})
                setattr(self,
                        class_name_lower,
                        getattr(module, class_name)(**subcomponent_kwargs))
            else:
                # Should have been passed either an instance of base_class or dict with subcomponent
                # configuration. Got something else...
                self.logger.error("Expected either a {} instance or dict, got {}".format(
                    class_name, subcomponent))
                setattr(self, class_name_lower, None)
        else:
            setattr(self, class_name_lower, None)

    def __str__(self):
        try:
            name = self.name
            if self.is_primary:
                name += ' [Primary]'

            s = f"{name} ({self.uid}) on {self.port}"

            sub_count = 0
            for sub_name in self._subcomponent_names:
                subcomponent = getattr(self, sub_name)
                if subcomponent:
                    if sub_count == 0:
                        s += f" with {subcomponent.name}"
                    else:
                        s += f" & {subcomponent.name}"
                    sub_count += 1
        except Exception:
            s = str(self.__class__)

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
