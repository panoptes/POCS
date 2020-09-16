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


class AbstractCamera(PanBase, metaclass=ABCMeta):
    """Base class for all cameras.

    Attributes:
        filter_type (str): Type of filter attached to camera. If a filterwheel is present this
            will return the filterwheel.current_filter property, otherwise it will return the
            value of the filter_type keyword argument, or if that argument was not given it
            it will query the camera driver, e.g. 'M' for unfiltered monochrome camera,
            'RGGB' for Bayer matrix colour camera.
        focuser (`panoptes.pocs.focuser.AbstractFocuser`|None): Focuser for the camera, default
            None.
        filter_wheel (`panoptes.pocs.filterwheel.AbstractFilterWheel`|None): Filter wheel for the
            camera, default None.
        uid (str): Unique identifier of the camera.
        is_primary (bool): If this camera is the primary camera for the system, default False.
        model (str): The model of camera, such as 'gphoto2', 'sbig', etc. Default 'simulator'.
        name (str): Name of the camera, default 'Generic Camera'.
        port (str): The port the camera is connected to, typically a usb device, default None.
        temperature (astropy.units.Quantity): Current temperature of the image sensor.
        target_temperature (astropy.units.Quantity): image sensor cooling target temperature.
        temperature_tolerance (astropy.units.Quantity): tolerance for image sensor temperature.
        cooling_enabled (bool): True if image sensor cooling is active.
        cooling_power (astropy.unit.Quantity): Current image sensor cooling power level in percent.
        egain (astropy.units.Quantity): Image sensor gain in e-/ADU as reported by the camera.
        gain (int): The gain setting of the camera (ZWO cameras only).
        bitdepth (astropy.units.Quantity): ADC bit depth in bits.
        image_type (str): Image format of the camera, e.g. 'RAW16', 'RGB24' (ZWO cameras only).
        timeout (astropy.units.Quantity): max time to wait after exposure before TimeoutError.
        readout_time (float): approximate time to readout the camera after an exposure.
        file_extension (str): file extension used by the camera's image data, e.g. 'fits'
        library_path (str): path to camera library, e.g. '/usr/local/lib/libfli.so' (SBIG, FLI, ZWO)
        properties (dict): A collection of camera properties as read from the camera.
        is_connected (bool): True if camera is connected.
        is_cooled_camera (bool): True if camera has image sensor cooling capability.
        is_temperature_stable (bool): True if image sensor temperature is stable.
        is_exposing (bool): True if an exposure is currently under way, otherwise False.
        is_ready (bool): True if the camera is ready to take an exposure.
        can_take_internal_darks (bool): True if the camera can take internal dark exposures.

    Notes:
        The port parameter is not used by SBIG or ZWO cameras, and is deprecated for FLI cameras.
        For these cameras serial_number should be passed to the constructor instead. For SBIG and
        FLI this should simply be the serial number engraved on the camera case, whereas for
        ZWO cameras this should be the 8 character ID string previously saved to the camera
        firmware.  This can be done using ASICAP,
        or `panoptes.pocs.camera.libasi.ASIDriver.set_ID()`.
    """

    _subcomponents = {
        'focuser': 'panoptes.pocs.focuser.focuser',
        'filterwheel': 'panoptes.pocs.filterwheel.filterwheel',
    }

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
        self._cooling_enabled = False
        self._is_temperature_stable = False
        self._temperature_thread = None
        self._restart_temperature_thread = False
        self.temperature_tolerance = kwargs.get('temperature_tolerance', 0.5 * u.Celsius)

        self._connected = False
        self._current_observation = None
        self._exposure_event = threading.Event()
        self._exposure_event.set()
        self._is_exposing = False
        self._exposure_error = None

        # By default assume camera isn't capable of internal darks.
        self._internal_darks = kwargs.get('internal_darks', False)

        # Set up any subcomponents.
        for subcomponent_name, subcomponent_class in self._subcomponents.items():
            # Create the subcomponent as an attribute with default None.
            setattr(self, subcomponent_name, None)
            subcomponent = kwargs.get(subcomponent_name)
            if subcomponent is not None:
                self._create_subcomponent(subcomponent=subcomponent, class_name=subcomponent_class)

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
    def target_temperature(self, target):
        """
        Set value of the CCD set point, the target temperature for the camera's image sensor
        cooling control.

        Note: this only needs to be implemented for cameras which have cooled image sensors,
        not for those that don't (e.g. DSLRs).
        """
        if not isinstance(target, u.Quantity):
            target = target * u.Celsius
        self.logger.debug(f"Setting {self} cooling set point to {target}.")

        self._set_target_temperature(target)

        if self.cooling_enabled:
            self._check_temperature_stability()

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
        self.logger.debug(f"Setting {self.name} cooling enabled to {enable}")
        self._set_cooling_enabled(enable)
        if self.cooling_enabled:
            self._check_temperature_stability()

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

            # Temperature must be within tolerance
            temp_difference = abs(self.temperature - self.target_temperature)
            at_target_temp = temp_difference <= self.temperature_tolerance

            # Camera cooling power must not be 100%
            cooling_at_maximum = get_quantity_value(self.cooling_power, u.percent) == 100

            # Also require temperature has been stable for some time
            # This private variable is set by _check_temperature_stability
            cooling_is_stable = self._is_temperature_stable

            temp_is_stable = at_target_temp and cooling_is_stable and not cooling_at_maximum

            if not temp_is_stable:
                self.logger.warning(f'Unstable CCD temperature in {self}.')
            self.logger.debug(f'Cooling power={self.cooling_power:.02f} '
                              f'Temperature={self.temperature:.02f} '
                              f'Target temp={self.target_temperature:.02f} '
                              f'Temp tol={self.temperature_tolerance:.02f} '
                              f"Temp diff={temp_difference:.02f} "
                              f"At target={at_target_temp} "
                              f"At max cooling={cooling_at_maximum} "
                              f"Cooling is stable={cooling_is_stable} "
                              f"Temperature is stable={temp_is_stable}")
            return temp_is_stable
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

    @property
    def can_take_internal_darks(self):
        """ True if the camera can take internal dark exposures.
        This will be true of cameras that have an internal mechanical shutter and can
        be commanded to keep that shutter closed during the exposure. For cameras that
        either lack a mechanical shutter or lack the option to keep it closed light must
        be kept out of the camera during dark exposures by other means, e.g. an opaque
        blank in a filterwheel, a lens cap, etc.
        """
        return self._internal_darks

    @property
    def exposure_error(self):
        """ Error message from the most recent exposure or None, if there was no error."""
        return self._exposure_error

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
        self._exposure_error = None

        if not self.is_connected:
            err = AssertionError("Camera must be connected for take_exposure!")
            self.logger.error(str(err))
            self._exposure_error = repr(err)
            raise err

        if not filename:
            err = AssertionError("Must pass filename for take_exposure")
            self.logger.error(str(err))
            self._exposure_error = repr(err)
            raise err

        if not self.can_take_internal_darks:
            if dark:
                try:
                    # Can't take internal dark, so try using an opaque filter in a filterwheel
                    self.filterwheel.move_to_dark_position(blocking=True)
                    self.logger.debug("Taking dark exposure using filter '"
                                      f"{self.filterwheel.filter_name(self.filterwheel._dark_position)}'.")
                except (AttributeError, error.NotFound):
                    # No filterwheel, or no opaque filter (dark_position not set)
                    self.logger.warning("Taking dark exposure without shutter or opaque filter. Is the lens cap on?")
            else:
                with suppress(AttributeError, error.NotFound):
                    # Ignoring exceptions from no filterwheel, or no last light position
                    self.filterwheel.move_to_light_position(blocking=True)

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
            err = error.PanError(f"Attempt to start exposure on {self} while not ready: +"
                                 f"{problems_string}.")
            self._exposure_error = repr(err)
            raise err

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

        self.logger.debug(f'Taking {seconds} exposure on {self.name}: {filename}')

        header = self._create_fits_header(seconds, dark)

        if not self._exposure_event.is_set():
            err = error.PanError(f"Attempt to take exposure on {self} while one already " +
                                 "in progress.")
            self._exposure_error = repr(err)
            raise err

        # Clear event now to prevent any other exposures starting before this one is finished.
        self._exposure_event.clear()

        try:
            # Camera type specific exposure set up and start
            readout_args = self._start_exposure(seconds, filename, dark, header, *args, *kwargs)
        except Exception as err:
            err = error.PanError("Error starting exposure on {}: {}".format(self, err))
            self._exposure_error = repr(err)
            self._exposure_event.set()
            raise err

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

        if not os.path.exists(file_path):
            self.logger.error(f"Expected image at '{file_path}' does not exist or " +
                              "cannot be accessed, cannot process.")
            observation_event.set()
            return

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
        kwargs['blocking'] = True
        self.take_exposure(seconds, filename=file_path, *args, **kwargs)
        if self.exposure_error is not None:
            raise error.PanError(self.exposure_error)
        image = fits.getdata(file_path)
        if not keep_file:
            os.unlink(file_path)
        return img_utils.crop_data(image, box_width=thumbnail_size)

    def _check_temperature_stability(self, required_stable_time=60 * u.second,
                                     sleep_delay=5 * u.second, timeout=300 * u.second,
                                     blocking=False):
        """
        Wait until camera temperature is within tolerance for a sufficiently long period of time.

        Args:
            required_stable_time (astropy.units.Quantity): Minimum consecutive amount of
                time to be considered stable. Default 60s.
            sleep_delay (astropy.units.Quantity): Time to sleep between checks. Default 10s.
            timeout (astropy.units.Quantity): Time before Timeout error is raised. Default 300s.
            blocking (bool): Block until stable temperature or timeout? Useful for testing.
        """
        # Convert all times to seconds
        sleep_delay = get_quantity_value(sleep_delay, u.second)
        required_stable_time = get_quantity_value(required_stable_time, u.second)
        timeout = get_quantity_value(timeout, u.second)

        # Define an inner function to run in a thread
        def check_temp(required_stable_time, sleep_delay, timeout):
            if required_stable_time > timeout:
                raise ValueError("required_stable_time must be less than timeout.")
            if sleep_delay > timeout:
                raise ValueError("sleep_delay must be less than timeout.")

            # Wait until stable temperature persists or timeout
            time_stable = 0
            timer = CountdownTimer(duration=timeout)
            while True:
                if timer.expired():
                    break
                # We may need to restart the thread before it has finished if another check has been requested.
                if self._restart_temperature_thread:
                    self._restart_temperature_thread = False
                    return
                # Check if the temperature is within tolerance
                if abs(self.temperature - self.target_temperature) < self.temperature_tolerance:
                    time_stable += sleep_delay
                    if time_stable >= required_stable_time:
                        self.logger.info(f"Temperature has stabilised on {self}.")
                        self._is_temperature_stable = True
                        return
                else:
                    time_stable = 0  # Reset the countdown
                time.sleep(sleep_delay)
            raise error.Timeout(f"Timeout while waiting for stable temperture on {self}.")

        # Restart countdown if one is already in progress
        if self._temperature_thread is not None:
            if self._temperature_thread.is_alive():
                self.logger.warning(f"Attempted to wait for stable temperature on {self}"
                                    " while wait already in progress. Restarting countdown.")
                self._restart_temperature_thread = True
                self._temperature_thread.join()

        # Wait for stable temperature
        self._is_temperature_stable = False
        self.logger.info(f"Waiting for stable temperature on {self}.")
        self._temperature_thread = threading.Thread(
            target=check_temp, args=(required_stable_time, sleep_delay, timeout))
        self._temperature_thread.start()
        if blocking:
            self._temperature_thread.join()

    @abstractmethod
    def _set_target_temperature(self, target):
        """Camera-specific function to set the target temperature.

        Note:
            Each sub-class is required to implement this abstract method. The derived
            method should at a minimum implement the described parameters.

        Args:
            target (astropy.units.Quantity): The target temperature.
        """
        raise NotImplementedError

    @abstractmethod
    def _set_cooling_enabled(self, enable):
        """Camera-specific function to set cooling enabled.

        Note:
            Each sub-class is required to implement this abstract method. The derived
            method should at a minimum implement the described parameters.

        Args:
            enable (bool): Enable camera cooling?
        """
        raise NotImplementedError

    @abstractmethod
    def _start_exposure(self, seconds=None, filename=None, dark=False, header=None, *args,
                        **kwargs):
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
        except Exception as err:
            # Error returned by driver at some point while polling
            self.logger.error(f'Error while waiting for exposure on {self}: {err!r}')
            self._exposure_error = repr(err)
            raise err
        else:
            # Camera type specific readout function
            try:
                self._readout(*readout_args)
            except Exception as err:
                self.logger.error(f"Error during readout on {self}: {err!r}")
                self._exposure_error = repr(err)
                raise err
        finally:
            # Make sure this gets set regardless of any errors
            self._exposure_event.set()

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
                    self.logger.debug(
                        f'Moving filterwheel={self.filterwheel} to filter_name='
                        f'{observation.filter_name}')
                    self.filterwheel.move_to(observation.filter_name, blocking=True)
                except Exception as e:
                    self.logger.error(f'Error moving filterwheel on {self} to'
                                      f' {observation.filter_name}: {e!r}')
                    raise (e)

            else:
                self.logger.info(f'Filter {observation.filter_name} requested by'
                                 f' observation but {self.filterwheel} is missing that filter, '
                                 f'using'
                                 f' {self.filter_type}.')

        if headers is None:
            start_time = current_time(flatten=True)
        else:
            start_time = headers.get('start_time', current_time(flatten=True))

        if not observation.seq_time:
            self.logger.debug(f'Setting observation seq_time={start_time}')
            observation.seq_time = start_time

        # Get the filename
        self.logger.debug(
            f'Setting image_dir={observation.directory}/{self.uid}/{observation.seq_time}')
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
            f'Observation setup: exptime={exptime} file_path={file_path} image_id={image_id} '
            f'metadata={metadata}')
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
        # Load the module for the subcomponent.
        try:
            self.logger.debug(f'Loading {class_name=} module')
            base_module = load_module(class_name)
        except error.NotFound as err:
            self.logger.critical(f"Couldn't import {class_name=} for {subcomponent=}!")
            raise err

        # Get the base class from the loaded module.
        base_class = getattr(base_module, f"Abstract{class_name}")

        if isinstance(subcomponent, base_class):
            self.logger.debug(f"{subcomponent=} is a {base_class=} instance, using it directly.")
            # Assign the subcomponent to the object attribute.
            setattr(self, class_name, subcomponent)
            # Give the subcomponent a reference back to the camera.
            getattr(self, class_name).camera = self
        elif isinstance(subcomponent, dict):
            self.logger.debug(f"{subcomponent=} is a dict, trying to create a {base_class=} instance.")
            try:
                module = load_module(subcomponent['model'])
            except (KeyError, error.NotFound) as err:
                self.logger.critical(f"Can't create a {class_name=} from {subcomponent=}")
                raise err
            # Copy dict creation items and add the camera.
            subcomponent_kwargs = copy.deepcopy(subcomponent)
            subcomponent_kwargs.update({'camera': self})
            self.logger.debug(f'Creating the {class_name=} object')
            subcomponent = getattr(module, class_name)(**subcomponent_kwargs)
            self.logger.info(f'{subcomponent=} created for {class_name=}, attaching to camera.')
            setattr(self, class_name, subcomponent)
        else:
            # Should have been passed either an instance of base_class or dict with subcomponent
            # configuration. Got something else...
            self.logger.error(f"Expected either a {class_name} instance or dict, got {subcomponent}")

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
        except Exception as e:
            self.logger.warning(f'Unable to stringify camera: {e=}')
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
