import copy
import os
import threading
import time
from abc import ABCMeta
from abc import abstractmethod
from contextlib import suppress

import astropy.units as u
from astropy.io import fits
from astropy.time import Time
from panoptes.pocs.base import PanBase
from panoptes.utils import error
from panoptes.utils import images as img_utils
from panoptes.utils.images import fits as fits_utils
from panoptes.utils.library import load_module
from panoptes.utils.time import CountdownTimer
from panoptes.utils.time import current_time
from panoptes.utils.utils import get_quantity_value


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

    _SUBCOMPONENT_LIST = {
        # attribute: full qualified namespace for base class.
        'focuser': 'panoptes.pocs.focuser.focuser.AbstractFocuser',
        'filterwheel': 'panoptes.pocs.filterwheel.filterwheel.AbstractFilterWheel',
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

        self.filterwheel = None
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
        self.temperature_tolerance = kwargs.get('temperature_tolerance', 0.5 * u.Celsius)
        self._cooling_required_table_time = None
        self._cooling_sleep_delay = None
        self._cooling_timeout = None

        self._connected = False
        self._current_observation = None
        self._is_exposing_event = threading.Event()
        self._exposure_error = None

        # By default assume camera isn't capable of internal darks.
        self._internal_darks = kwargs.get('internal_darks', False)

        # Set up any subcomponents.
        self.subcomponents = dict()
        for attr_name, class_path in self._SUBCOMPONENT_LIST.items():
            # Create the subcomponent as an attribute with default None.
            self.logger.debug(f'Setting default attr_name={attr_name!r} to None')
            setattr(self, attr_name, None)

            # If given subcomponent class (or dict), try to create instance.
            subcomponent = kwargs.get(attr_name)
            if subcomponent is not None:
                self.logger.debug(f'Found subcomponent={subcomponent!r}, creating instance')

                subcomponent = self._create_subcomponent(class_path, subcomponent)
                self.logger.debug(
                    f'Assigning subcomponent={subcomponent!r} to attr_name={attr_name!r}')
                setattr(self, attr_name, subcomponent)
                # Keep a list of active subcomponents
                self.subcomponents[attr_name] = subcomponent

        # Apply the initial focus offset
        # This is required so that the focuser initial position corresponds to focus_offset=0
        if self.has_focuser and self.has_filterwheel:
            current_filter = self.filterwheel.current_filter
            focus_offset = self.filterwheel.focus_offsets.get(current_filter, 0)
            self.logger.debug(f"Initial focus offset for {current_filter} filter: {focus_offset}")
            if focus_offset:
                self.focuser.move_by(focus_offset)

        self.logger.debug(f'Camera created: {self}')

    ############################################################################
    # Properties
    ############################################################################

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
        if self.has_filterwheel:
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

            temp_is_stable = at_target_temp and not cooling_at_maximum

            if not temp_is_stable:
                self.logger.warning(f'Unstable CCD temperature in {self}.')
            self.logger.debug(f'Cooling power={self.cooling_power:.02f} '
                              f'Temperature={self.temperature:.02f} '
                              f'Target temp={self.target_temperature:.02f} '
                              f'Temp tol={self.temperature_tolerance:.02f} '
                              f"Temp diff={temp_difference:.02f} "
                              f"At target={at_target_temp} "
                              f"At max cooling={cooling_at_maximum} "
                              f"Temperature is stable={temp_is_stable}")
            return temp_is_stable
        else:
            return False

    @property
    def is_exposing(self):
        """ True if an exposure is currently under way, otherwise False. """
        return self._is_exposing_event.is_set()

    @property
    def readiness(self):
        """ Dictionary detailing the readiness of the camera system to take an exposure. """
        current_readiness = {}
        # For cooled camera expect stable temperature before taking exposure
        if self.is_cooled_camera:
            current_readiness['temperature_stable'] = self.is_temperature_stable
        # Check all the subcomponents too, e.g. make sure filterwheel/focuser aren't moving.
        for sub_name, subcomponent in self.subcomponents.items():
            current_readiness[sub_name] = subcomponent.is_ready

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
        for sub_name, subcomponent in self.subcomponents.items():
            if not current_readiness.get(sub_name, True):
                self.logger.warning(f"Camera {self} not ready: {sub_name} not ready.")

        # Make sure there isn't an exposure already in progress.
        if not current_readiness.get('not_exposing', True):
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

    @property
    def has_focuser(self):
        """ Return True if the camera has a focuser, False if not. """
        return self.focuser is not None

    @property
    def has_filterwheel(self):
        """ Return True if the camera has a filterwheel, False if not. """
        return self.filterwheel is not None

    ############################################################################
    # Methods
    ############################################################################

    @abstractmethod
    def connect(self):
        raise NotImplementedError  # pragma: no cover

    def take_observation(self, observation, headers=None, filename=None, blocking=False, **kwargs):
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
                override the default file naming system.
            blocking (bool): If method should wait for observation event to be complete
                before returning, default False.
            **kwargs (dict): Optional keyword arguments (`exptime`, dark)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        observation_event = threading.Event()
        # Setup the observation
        exptime, file_path, image_id, metadata = self._setup_observation(observation,
                                                                         headers,
                                                                         filename,
                                                                         **kwargs)

        # pop exptime from kwarg as its now in exptime
        exptime = kwargs.pop('exptime', observation.exptime.value)

        # start the exposure
        self.take_exposure(seconds=exptime, filename=file_path, blocking=blocking,
                           dark=observation.dark, **kwargs)

        # Add most recent exposure to list
        if self.is_primary:
            if 'POINTING' in metadata:
                observation.pointing_images[image_id] = file_path
            else:
                observation.exposure_list[image_id] = file_path

        # Process the exposure once readout is complete
        # To be used for marking when exposure is complete (see `process_exposure`)
        t = threading.Thread(
            name=f'Thread-{image_id}',
            target=self.process_exposure,
            args=(metadata, observation_event),
            daemon=True)
        t.start()

        if blocking:
            while not observation_event.is_set():
                self.logger.trace(f'Waiting for observation event')
                time.sleep(0.5)

        return observation_event

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      timeout=None,
                      *args,
                      **kwargs) -> threading.Thread:
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
                the exposure, if True will block until it completes and file exists.
            timeout (astropy.Quantity): The timeout to use for the exposure. If None, will be
                calculated automatically.
        Returns:
            threading.Thread: The readout thread, which joins when readout has finished.
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
                    self.logger.debug("Taking dark exposure using filter: " +
                                      self.filterwheel.filter_name(self.filterwheel._dark_position))
                except (AttributeError, error.NotFound):
                    # No filterwheel, or no opaque filter (dark_position not set)
                    self.logger.warning("Taking dark exposure without shutter or opaque filter."
                                        " Is the lens cap on?")
            else:
                with suppress(AttributeError, error.NotFound):
                    # Ignoring exceptions from no filterwheel, or no last light position
                    self.filterwheel.move_to_light_position(blocking=True)

        # Check that the camera (and subcomponents) is ready
        if not self.is_ready:
            # Work out why the camera isn't ready.
            self.logger.warning(f'Cameras not ready: {self.readiness!r}')
            raise error.PanError(f"Attempt to start exposure on {self} while not ready.")

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

        self.logger.debug(f'Taking {seconds=!r} exposure on {self.name}: {filename=!r}')

        header = self._create_fits_header(seconds, dark)

        if self.is_exposing:
            err = error.PanError(
                f"Attempt to take exposure on {self} while one already in progress.")
            self._exposure_error = repr(err)
            raise err

        try:
            # Camera type specific exposure set up and start
            self._is_exposing_event.set()
            readout_args = self._start_exposure(seconds=seconds, filename=filename, dark=dark,
                                                header=header, *args, **kwargs)
        except Exception as err:
            err = error.PanError(f"Error starting exposure on {self}: {err!r}")
            self._exposure_error = repr(err)
            self._is_exposing_event.clear()
            raise err

        def log_thread_error(exc_info):
            self.logger.error(f'{exc_info!r}')

        threading.excepthook = log_thread_error

        # Start polling thread that will call camera type specific _readout method when done
        readout_thread = threading.Thread(target=self._poll_exposure,
                                          args=(readout_args, seconds),
                                          kwargs=dict(timeout=timeout))
        readout_thread.start()

        if blocking:
            self.logger.debug(f"Blocking on exposure event for {self}")
            readout_thread.join()
            while self.is_exposing:
                time.sleep(0.5)
            self.logger.trace(f'Exposure blocking complete, waiting for file to exist')
            while not os.path.exists(filename):
                time.sleep(0.1)
            self.logger.debug(f"Blocking complete on {self} for filename={filename!r}")

        return readout_thread

    def process_exposure(self,
                         metadata,
                         observation_event,
                         compress_fits=None,
                         record_observations=None,
                         make_pretty_images=None):
        """ Processes the exposure.

        Performs the following steps:

            1. First checks to make sure that the file exists on the file system.
            2. Calls `_process_fits` with the filename and info, which is specific to each camera.
            3. Makes pretty images if requested.
            4. Records observation metadata if requested.
            5. Compresses FITS files if requested.
            6. Sets the observation_event.

        If the camera is a primary camera, extract the jpeg image and save metadata to database
        `current` collection. Saves metadata to `observations` collection for all images.

        Args:
            metadata (dict): Header metadata saved for the image
            observation_event (threading.Event): An event that is set signifying that the
                camera is done with this exposure
            compress_fits (bool or None): If FITS files should be fpacked into .fits.fz.
                If None (default), checks the `observations.compress_fits` config-server key.
            record_observations (bool or None): If observation metadata should be saved.
                If None (default), checks the `observations.record_observations`
                config-server key.
            make_pretty_images (bool or None): If should make a jpg from raw image.
                If None (default), checks the `observations.make_pretty_images`
                config-server key.

        Raises:
            FileNotFoundError: If the FITS file isn't at the specified location.
        """
        # Wait for exposure to complete. Timeout handled by exposure thread.
        while self.is_exposing:
            time.sleep(1)

        self.logger.debug(f'Starting exposure processing for {observation_event}')

        if compress_fits is None:
            compress_fits = self.get_config('observations.compress_fits', default=False)

        if make_pretty_images is None:
            make_pretty_images = self.get_config('observations.make_pretty_images', default=False)

        image_id = metadata['image_id']
        seq_id = metadata['sequence_id']
        file_path = metadata['file_path']
        exptime = metadata['exptime']
        field_name = metadata['field_name']

        # Make sure image exists.
        if not os.path.exists(file_path):
            observation_event.set()
            raise FileNotFoundError(
                f"Expected image at {file_path=!r} does not exist or " +
                "cannot be accessed, cannot process.")

        self.logger.debug(f'Starting FITS processing for {file_path}')
        file_path = self._process_fits(file_path, metadata)
        self.logger.debug(f'Finished FITS processing for {file_path}')

        # TODO make this async and take it out of camera.
        if make_pretty_images:
            try:
                image_title = f'{field_name} [{exptime}s] {seq_id}'

                self.logger.debug(f"Making pretty image for file_path={file_path!r}")
                link_path = None
                if metadata['is_primary']:
                    # This should be in the config somewhere.
                    link_path = os.path.expandvars('$PANDIR/images/latest.jpg')

                img_utils.make_pretty_image(file_path,
                                            title=image_title,
                                            link_path=link_path)
            except Exception as e:  # pragma: no cover
                self.logger.warning(f'Problem with extracting pretty image: {e!r}')

        metadata['exptime'] = get_quantity_value(metadata['exptime'], unit='second')

        if record_observations:
            self.logger.debug(f"Adding current observation to db: {image_id}")
            self.db.insert_current('observations', metadata)

        if compress_fits:
            self.logger.debug(f'Compressing file_path={file_path!r}')
            compressed_file_path = fits_utils.fpack(file_path)
            self.logger.debug(f'Compressed {compressed_file_path}')

        # Mark the event as done
        observation_event.set()

    def autofocus(self,
                  seconds=None,
                  focus_range=None,
                  focus_step=None,
                  cutout_size=None,
                  keep_files=None,
                  take_dark=None,
                  merit_function='vollath_F4',
                  merit_function_kwargs=None,
                  mask_dilations=None,
                  coarse=False,
                  make_plots=None,
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
            cutout_size (int, optional): Size of square central region of image
                to use, default 500 x 500 pixels.
            keep_files (bool, optional): If True will keep all images taken
                during focusing. If False (default) will delete all except the
                first and last images from each focus run.
            take_dark (bool, optional): If True will attempt to take a dark frame
                before the focus run, and use it for dark subtraction and hot
                pixel masking, default True.
            merit_function (str/callable, optional): Merit function to use as a
                focus metric, default vollath_F4.
            merit_function_kwargs (dict or None, optional): Dictionary of additional
                keyword arguments for the merit function.
            mask_dilations (int, optional): Number of iterations of dilation to perform on the
                saturated pixel mask (determine size of masked regions), default 10
            coarse (bool, optional): Whether to perform a coarse focus, otherwise will perform
                a fine focus. Default False.
            make_plots (bool, optional: Whether to write focus plots to images folder, default
                behaviour is to check the focuser autofocus_make_plots attribute.
            blocking (bool, optional): Whether to block until autofocus complete, default False.

        Returns:
            threading.Event: Event that will be set when autofocusing is complete

        Raises:
            ValueError: If invalid values are passed for any of the focus parameters.
        """
        if not self.has_focuser:
            self.logger.error("Camera must have a focuser for autofocus!")
            raise AttributeError

        return self.focuser.autofocus(seconds=seconds,
                                      focus_range=focus_range,
                                      focus_step=focus_step,
                                      keep_files=keep_files,
                                      take_dark=take_dark,
                                      cutout_size=cutout_size,
                                      merit_function=merit_function,
                                      merit_function_kwargs=merit_function_kwargs,
                                      mask_dilations=mask_dilations,
                                      coarse=coarse,
                                      make_plots=make_plots,
                                      blocking=blocking,
                                      *args, **kwargs)

    def get_cutout(self, seconds, file_path, cutout_size, keep_file=False, *args, **kwargs):
        """
        Takes an image and returns a thumbnail cutout.

        Takes an image, grabs the data, deletes the FITS file and
        returns a cutout from the centre of the image.

        Args:
            seconds (astropy.units.Quantity): exposure time, Quantity or numeric type in seconds.
            file_path (str): path to (temporarily) save the image file to.
            cutout_size (int): size of the square region of the centre of the image to return.
            keep_file (bool, optional): if True the image file will be deleted, if False it will
                be kept.
            *args, **kwargs: passed to the `take_exposure` method
        """
        kwargs['blocking'] = True
        self.take_exposure(seconds, filename=file_path, *args, **kwargs)
        if self.exposure_error is not None:
            raise error.PanError(self.exposure_error)
        image = fits.getdata(file_path)
        if not keep_file:
            os.unlink(file_path)

        # Make sure cutout is not bigger than image.
        actual_size = min(cutout_size, *image.shape)
        if actual_size != cutout_size:  # noqa
            self.logger.warning(f'Requested cutout size is larger than image, using {actual_size}')

        return img_utils.crop_data(image, box_width=cutout_size)

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

    def _set_cooling_enabled(self, enable):
        """Camera-specific function to set cooling enabled.

        Note:
            Each sub-class is required to implement this abstract method. The derived
            method should at a minimum implement the described parameters.

        Args:
            enable (bool): Enable camera cooling?
        """
        self._cooling_enabled = enable

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

    def _poll_exposure(self, readout_args, exposure_time, timeout=None, interval=0.01):
        """ Wait until camera is no longer exposing or the timeout is reached.

        If the timeout is reached, an `error.Timeout` is raised.
        """
        if timeout is None:
            timer_duration = self._timeout + self._readout_time + exposure_time.to_value(u.second)
        else:
            timer_duration = timeout
        self.logger.debug(f"Polling exposure with timeout of {timer_duration} seconds.")
        timer = CountdownTimer(duration=timer_duration)
        try:
            while self.is_exposing:
                if timer.expired():
                    msg = f"Timeout ({timer.duration=}) waiting for exposure on {self}"
                    raise error.Timeout(msg)
                time.sleep(interval)
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
            self._is_exposing_event.clear()

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

        for sub_name, subcomponent in self.subcomponents.items():
            header = subcomponent._add_fits_keywords(header)

        return header

    def _setup_observation(self, observation, headers, filename, **kwargs):
        headers = headers or None

        # Move the filterwheel if necessary
        if self.has_filterwheel:
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

            elif not observation.dark:
                self.logger.warning(f'Filter {observation.filter_name} requested by'
                                    f' observation but {self.filterwheel} is missing that filter, '
                                    f'using {self.filter_type}.')

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

        # The exptime header data is set as part of observation but can
        # be overridden by passed parameter so update here.
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
            self.logger.trace(f'Updating {file_path} metadata with provided headers')
            metadata.update(headers)

        self.logger.debug(
            f'Observation setup: exptime={exptime!r} file_path={file_path!r} image_id={image_id!r} metadata='
            f'{metadata!r}')

        return exptime, file_path, image_id, metadata

    def _process_fits(self, file_path, metadata):
        """
        Add FITS headers from metadata the same as images.cr2_to_fits()
        """
        # TODO (wtgee) I don't like this one bit.
        fields = {
            'image_id': {'keyword': 'IMAGEID'},
            'sequence_id': {'keyword': 'SEQID'},
            'field_name': {'keyword': 'FIELD'},
            'ra_mnt': {'keyword': 'RA-MNT', 'comment': 'Degrees'},
            'ha_mnt': {'keyword': 'HA-MNT', 'comment': 'Degrees'},
            'dec_mnt': {'keyword': 'DEC-MNT', 'comment': 'Degrees'},
            'equinox': {'keyword': 'EQUINOX', 'default': 2000.},
            'airmass': {'keyword': 'AIRMASS', 'comment': 'Sec(z)'},
            'filter': {'keyword': 'FILTER'},
            'latitude': {'keyword': 'LAT-OBS', 'comment': 'Degrees'},
            'longitude': {'keyword': 'LONG-OBS', 'comment': 'Degrees'},
            'elevation': {'keyword': 'ELEV-OBS', 'comment': 'Meters'},
            'moon_separation': {'keyword': 'MOONSEP', 'comment': 'Degrees'},
            'moon_fraction': {'keyword': 'MOONFRAC'},
            'creator': {'keyword': 'CREATOR', 'comment': 'POCS Software version'},
            'camera_uid': {'keyword': 'INSTRUME', 'comment': 'Camera ID'},
            'observer': {'keyword': 'OBSERVER', 'comment': 'PANOPTES Unit ID'},
            'origin': {'keyword': 'ORIGIN'},
            'tracking_rate_ra': {'keyword': 'RA-RATE', 'comment': 'RA Tracking Rate'},
        }

        self.logger.debug(f"Updating FITS headers: {file_path} with metadata={metadata!r}")
        with fits.open(file_path, 'update') as f:
            hdu = f[0]
            for metadata_key, field_info in fields.items():
                fits_key = field_info['keyword']
                fits_comment = field_info.get('comment', '')
                # Get the value from either the metadata, the default, or use blank string.
                fits_value = metadata.get(metadata_key, field_info.get('default', ''))

                self.logger.trace(
                    f'Setting fits_key={fits_key!r} = fits_value={fits_value!r} fits_comment={fits_comment!r}')
                hdu.header.set(fits_key, fits_value, fits_comment)

            self.logger.debug(f"Finished FITS headers: {file_path}")

        return file_path

    def _create_subcomponent(self, class_path, subcomponent):
        """
        Creates a subcomponent as an attribute of the camera. Can do this from either an instance
        of the appropriate subcomponent class, or from a dictionary of keyword arguments for the
        subcomponent class' constructor.

        Args:
            subcomponent (instance of sub_name | dict): the subcomponent object, or the keyword
                arguments required to create it.
            class_path (str): Full namespace of the subcomponent, e.g.
                'panoptes.pocs.focuser.focuser.AbstractFocuser'.

        Returns:
            object: an instance of the subcomponent object.

        Raises:
            panoptes.utils.error.NotFound: Not found error.
        """
        # Load the module for the subcomponent.
        sub_parts = class_path.split('.')
        base_class_name = sub_parts.pop()
        base_module_name = '.'.join(sub_parts)
        self.logger.debug(f'Loading base_module_name={base_module_name!r}')
        try:
            base_module = load_module(base_module_name)
        except error.NotFound as err:
            self.logger.critical(f"Couldn't import base_module_name={base_module_name!r}")
            raise err

        # Get the base class from the loaded module.
        self.logger.debug(f'Trying to get base_class_name={base_class_name!r} from {base_module}')
        base_class = getattr(base_module, base_class_name)

        # If we get an instance, just use it.
        if isinstance(subcomponent, base_class):
            self.logger.debug(
                f"subcomponent={subcomponent!r} is already a base_class={base_class!r} instance")
        # If we get a dict, use them as params to create instance.
        elif isinstance(subcomponent, dict):
            try:
                model = subcomponent['model']
                self.logger.debug(
                    f"subcomponent={subcomponent!r} is a dict but has model={model!r} keyword, "
                    f"trying to create a base_class={base_class!r} instance")
                base_class = load_module(model)
            except (KeyError, error.NotFound) as err:
                raise error.NotFound(
                    f"Can't create a class_path={class_path!r} from subcomponent={subcomponent!r}")

            self.logger.debug(f'Creating the base_class_name={base_class_name!r} object from dict')

            # Copy dict creation items and add the camera.
            subcomponent_kwargs = copy.deepcopy(subcomponent)
            subcomponent_kwargs.update({'camera': self})

            try:
                subcomponent = base_class(**subcomponent_kwargs)
            except TypeError:
                raise error.NotFound(f'base_class={base_class!r} is not a callable class. '
                                     f'Please specify full path to class (not module).')
            self.logger.success(f'{subcomponent} created for {base_class_name}')
        else:
            # Should have been passed either an instance of base_class or dict with subcomponent
            # configuration. Got something else...
            raise error.NotFound(
                f"Expected either a {base_class_name} instance or dict, got {subcomponent!r}")

        # Give the subcomponent a reference back to the camera.
        setattr(subcomponent, 'camera', self)
        return subcomponent

    def __str__(self):
        s = f'{self.name}'
        try:
            if self.is_primary:
                s += ' [Primary]'

            s += f" ({self.uid})"

            if self.port:
                s += f" port={self.port}"

            sub_names = '& '.join(list(self.subcomponents.keys()))
            if sub_names != '':
                s += f" with {sub_names}"

        except Exception as e:
            self.logger.warning(f'Unable to stringify camera: e={e!r}')
            s = str(self.__class__)

        return s
