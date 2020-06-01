import os
import subprocess
from collections import OrderedDict
import pendulum

from astropy import units as u
from astropy.coordinates import get_moon
from astropy.coordinates import get_sun

from panoptes.pocs.base import PanBase
from panoptes.pocs.camera import AbstractCamera
from panoptes.pocs.dome import AbstractDome
from panoptes.pocs.images import Image
from panoptes.pocs.mount import AbstractMount
from panoptes.pocs.scheduler import BaseScheduler
from panoptes.pocs.utils.location import create_location_from_config

from panoptes.utils import current_time
from panoptes.utils import error


class Observatory(PanBase):

    def __init__(self, cameras=None, scheduler=None, dome=None, mount=None, *args, **kwargs):
        """Main Observatory class

        Starts up the observatory. Reads config file, sets up location,
        dates and weather station. Adds cameras, scheduler, dome and mount.
        """
        super().__init__(*args, **kwargs)
        self.logger.info('Initializing observatory')

        # Setup information about site location
        self.logger.info('Setting up location')
        site_details = create_location_from_config(config_port=self.config_port)
        self.location = site_details['location']
        self.earth_location = site_details['earth_location']
        self.observer = site_details['observer']

        # Do some one-time calculations
        now = current_time()
        self._local_sun_pos = self.observer.altaz(now, target=get_sun(now)).alt  # Re-calculated
        self._local_sunrise = self.observer.sun_rise_time(now)
        self._local_sunset = self.observer.sun_set_time(now)
        self._evening_astro_time = self.observer.twilight_evening_astronomical(now, which='next')
        self._morning_astro_time = self.observer.twilight_morning_astronomical(now, which='next')

        # Set up some of the hardware.
        self.set_mount(mount)
        self.cameras = OrderedDict()

        self._primary_camera = None
        if cameras:
            self.logger.info(f'Adding the cameras to the observatory: {cameras}')
            for cam_name, camera in cameras.items():
                self.add_camera(cam_name, camera)

        # TODO(jamessynge): Figure out serial port validation behavior here compared to that for the mount.
        self.set_dome(dome)

        self.set_scheduler(scheduler)
        self.current_offset_info = None

        self._image_dir = self.get_config('directories.images')

        self.logger.success('Observatory initialized')

    ##########################################################################
    # Helper methods
    ##########################################################################

    def is_dark(self, horizon='observe', default_dark=-18 * u.degree, at_time=None):
        """If sun is below horizon.

        Args:
            horizon (str, optional): Which horizon to use, 'flat', 'focus', or
                'observe' (default).
            default_dark (`astropy.unit.Quantity`, optional): The default horizon
                for when it is considered "dark". Default is astronomical twilight,
                -18 degrees.
            at_time (None or `astropy.time.Time`, optional): Time at which to
                check if dark, defaults to now.

        Returns:
            bool: If it is dark or not.
        """
        if at_time is None:
            at_time = current_time()

        horizon_deg = self.get_config(f'location.{horizon}_horizon', default=default_dark)
        is_dark = self.observer.is_night(at_time, horizon=horizon_deg)

        self._local_sun_pos = self.observer.altaz(at_time, target=get_sun(at_time)).alt
        self.logger.debug(f"Sun {self._local_sun_pos:.02f} > {horizon_deg} [{horizon}]")

        return is_dark

    ##########################################################################
    # Properties
    ##########################################################################

    @property
    def sidereal_time(self):
        return self.observer.local_sidereal_time(current_time())

    @property
    def has_cameras(self):
        return len(self.cameras) > 0

    @property
    def primary_camera(self):
        """Return primary camera.

        Note:
            If no camera has been marked as primary this will set and return
            the first camera in the OrderedDict as primary.

        Returns:
            `pocs.camera.Camera`: The primary camera.
        """
        if not self._primary_camera and self.has_cameras:
            self._primary_camera = self.cameras[list(self.cameras.keys())[0]]

        return self._primary_camera

    @primary_camera.setter
    def primary_camera(self, cam):
        cam.is_primary = True
        self._primary_camera = cam

    @property
    def current_observation(self):
        if self.scheduler is None:
            self.logger.info(f'Scheduler not present, cannot get current observation.')
            return None
        return self.scheduler.current_observation

    @current_observation.setter
    def current_observation(self, new_observation):
        if self.scheduler is None:
            self.logger.info(f'Scheduler not present, cannot set current observation.')
        else:
            self.scheduler.current_observation = new_observation

    @property
    def has_dome(self):
        return self.dome is not None

    @property
    def can_observe(self):
        """A dynamic property indicating whether or not observations are possible.

        This property will check to make sure that the following are present:
          * Scheduler
          * Cameras
          * Mount

        If any of the above are not present then a log message is generated and
        the property returns False.

        Returns:
            bool: True if observations are possible, False otherwise.
        """
        checks = {
            'scheduler': self.scheduler is not None,
            'cameras': self.has_cameras is True,
            'mount': self.mount is not None,
        }

        can_observe = all(checks.values())

        if can_observe is False:
            for check_name, is_true in checks.items():
                if not is_true:
                    self.logger.warning(f'{check_name.title()} not present, cannot observe')

        return can_observe

    ##########################################################################
    # Device Getters/Setters
    ##########################################################################

    def add_camera(self, cam_name, camera):
        """Add camera to list of cameras as cam_name.

        Args:
            cam_name (str): The name to use for the camera, e.g. `Cam00`.
            camera (`pocs.camera.camera.Camera`): An instance of the `~Camera` class.
        """
        assert isinstance(camera, AbstractCamera)
        self.logger.debug(f'Adding {cam_name}: {camera}')
        if cam_name in self.cameras:
            self.logger.debug(f'{cam_name} already exists, replacing existing camera under that name.')

        self.cameras[cam_name] = camera
        if camera.is_primary:
            self.primary_camera = camera

    def remove_camera(self, cam_name):
        """Remove cam_name from list of attached cameras.

        Note:
            If you remove and then add a camera you will change the index order
            of the camera. If you prefer to keep the same order then use `add_camera`
            with the same name as an existing camera to to update the list and preserve
            the order.

        Args:
            cam_name (str): Name of camera to remove.
        """
        self.logger.debug('Removing {}'.format(cam_name))
        del self.cameras[cam_name]

    def set_scheduler(self, scheduler):
        """Sets the scheduler for the `Observatory`.
        Args:
            scheduler (`pocs.scheduler.BaseScheduler`): An instance of the `~BaseScheduler` class.
        """
        if isinstance(scheduler, BaseScheduler):
            self.logger.info('Adding scheduler.')
            self.scheduler = scheduler
        elif scheduler is None:
            self.logger.info('Removing scheduler.')
            self.scheduler = None
        else:
            raise TypeError("Scheduler is not instance of BaseScheduler class, cannot add.")

    def set_dome(self, dome):
        """Set's dome or remove the dome for the `Observatory`.
        Args:
            dome (`pocs.dome.AbstractDome`): An instance of the `~AbstractDome` class.
        """
        if isinstance(dome, AbstractDome):
            self.logger.info('Adding dome.')
            self.dome = dome
        elif dome is None:
            self.logger.info('Removing dome.')
            self.dome = None
        else:
            raise TypeError('Dome is not instance of AbstractDome class, cannot add.')

    def set_mount(self, mount):
        """Sets the mount for the `Observatory`.
        Args:
            mount (`pocs.mount.AbstractMount`): An instance of the `~AbstractMount` class.
        """
        if isinstance(mount, AbstractMount):
            self.logger.info('Adding mount')
            self.mount = mount
        elif mount is None:
            self.logger.info('Removing mount')
            self.mount = None
        else:
            raise TypeError("Mount is not instance of AbstractMount class, cannot add.")

    ##########################################################################
    # Methods
    ##########################################################################

    def initialize(self):
        """Initialize the observatory and connected hardware """
        self.logger.debug("Initializing mount")
        self.mount.initialize()
        if self.dome:
            self.dome.connect()

    def power_down(self):
        """Power down the observatory. Currently does nothing
        """
        self.logger.debug("Shutting down observatory")
        if self.mount:
            self.mount.disconnect()
        if self.dome:
            self.dome.disconnect()

    @property
    def status(self):
        """Get status information for various parts of the observatory."""
        status = {'can_observe': self.can_observe}

        now = current_time()

        try:
            if self.mount.is_initialized:
                status['mount'] = self.mount.status
                current_coords = self.mount.get_current_coordinates()
                status['mount']['current_ha'] = self.observer.target_hour_angle(now, current_coords)
                if self.mount.has_target:
                    target_coords = self.mount.get_target_coordinates()
                    status['mount']['mount_target_ha'] = self.observer.target_hour_angle(now, target_coords)
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Can't get mount status: {e!r}")

        try:
            if self.dome:
                status['dome'] = self.dome.status
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Can't get dome status: {e!r}")

        try:
            if self.current_observation:
                status['observation'] = self.current_observation.status
                status['observation']['field_ha'] = self.observer.target_hour_angle(now, self.current_observation.field)
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Can't get observation status: {e!r}")

        try:
            status['observer'] = {
                'siderealtime': str(self.sidereal_time),
                'utctime': now,
                'localtime': pendulum.now(),
                'local_evening_astro_time': self._evening_astro_time,
                'local_morning_astro_time': self._morning_astro_time,
                'local_sun_set_time': self._local_sunset,
                'local_sun_rise_time': self._local_sunrise,
                'local_sun_position': self._local_sun_pos,
                'local_moon_alt': self.observer.moon_altaz(now).alt,
                'local_moon_illumination': self.observer.moon_illumination(now),
                'local_moon_phase': self.observer.moon_phase(now),
            }

        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Can't get time status: {e!r}")

        return status

    def get_observation(self, *args, **kwargs):
        """Gets the next observation from the scheduler

        Returns:
            observation (pocs.scheduler.observation.Observation or None): An
                an object that represents the observation to be made

        Raises:
            error.NoObservation: If no valid observation is found
        """

        self.logger.debug("Getting observation for observatory")

        if not self.scheduler:
            self.logger.info(f'Scheduler not present, cannot get the next observation.')
            return None

        # If observation list is empty or a reread is requested
        reread_fields_file = (
                self.scheduler.has_valid_observations is False or
                kwargs.get('reread_fields_file', False) or
                self.get_config('scheduler.check_file', default=False)
        )

        # This will set the `current_observation`
        self.scheduler.get_observation(reread_fields_file=reread_fields_file, *args, **kwargs)

        if self.current_observation is None:
            self.scheduler.clear_available_observations()
            raise error.NoObservation("No valid observations found")

        return self.current_observation

    def cleanup_observations(self, upload_images=None, make_timelapse=None, keep_jpgs=None):
        """Cleanup observation list

        Loops through the `observed_list` performing cleanup tasks. Resets
        `observed_list` when done.

        Args:
            upload_images (None or bool, optional): If images should be uploaded to a Google
                Storage bucket, default to config item `panoptes_network.image_storage` then False.
            make_timelapse (None or bool, optional): If a timelapse should be created
                (requires ffmpeg), default to config item `observations.make_timelapse` then True.
            keep_jpgs (None or bool, optional): If JPG copies of observation images should be kept
                on local hard drive, default to config item `observations.keep_jpgs` then True.
        """
        if upload_images is None:
            upload_images = self.get_config('panoptes_network.image_storage', default=False)

        if make_timelapse is None:
            make_timelapse = self.get_config('observations.make_timelapse', default=True)

        if keep_jpgs is None:
            keep_jpgs = self.get_config('observations.keep_jpgs', default=True)

        process_script = 'upload-image-dir.py'
        process_script_path = os.path.join(os.environ['POCS'], 'scripts', process_script)

        if self.scheduler is None:
            self.logger.info(f'Scheduler not present, cannot finish cleanup.')
            return

        for seq_time, observation in self.scheduler.observed_list.items():
            self.logger.debug("Housekeeping for {}".format(observation))

            observation_dir = os.path.join(
                self._image_dir,
                'fields',
                observation.field.field_name
            )
            self.logger.debug('Searching directory: {}', observation_dir)

            for cam_name, camera in self.cameras.items():
                self.logger.debug('Cleanup for camera {} [{}]'.format(
                    cam_name, camera.uid))

                seq_dir = os.path.join(
                    observation_dir,
                    camera.uid,
                    seq_time
                )
                self.logger.info('Cleaning directory {}'.format(seq_dir))

                process_cmd = [
                    process_script_path,
                    '--directory', seq_dir,
                ]

                if upload_images:
                    process_cmd.append('--upload')

                if make_timelapse:
                    process_cmd.append('--make-timelapse')

                if keep_jpgs is False:
                    process_cmd.append('--remove-jpgs')

                # Start the subprocess in background and collect proc object.
                clean_proc = subprocess.Popen(process_cmd,
                                              universal_newlines=True,
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE
                                              )
                self.logger.info('Cleaning directory pid={}'.format(clean_proc.pid))

                # Block and wait for directory to finish
                try:
                    outs, errs = clean_proc.communicate(timeout=3600)  # one hour
                    if outs and outs > '':
                        self.logger.info(f'Output from clean: {outs}')
                    if errs and errs > '':
                        self.logger.info(f'Errors from clean: {errs}')
                except Exception as e:  # pragma: no cover
                    self.logger.error(f'Error during cleanup_observations: {e!r}')
                    clean_proc.kill()
                    outs, errs = clean_proc.communicate(timeout=10)
                    if outs and outs > '':
                        self.logger.info(f'Output from clean: {outs}')
                    if errs and errs > '':
                        self.logger.info(f'Errors from clean: {errs}')

            self.logger.debug('Cleanup finished')

        self.scheduler.reset_observed_list()

    def observe(self):
        """Take individual images for the current observation

        This method gets the current observation and takes the next
        corresponding exposure.

        """
        # Get observatory metadata
        headers = self.get_standard_headers()

        # All cameras share a similar start time
        headers['start_time'] = current_time(flatten=True)

        # List of camera events to wait for to signal exposure is done
        # processing
        camera_events = dict()

        # Take exposure with each camera
        for cam_name, camera in self.cameras.items():
            self.logger.debug("Exposing for camera: {}".format(cam_name))

            try:
                # Start the exposures
                cam_event = camera.take_observation(self.current_observation, headers)

                camera_events[cam_name] = cam_event

            except Exception as e:
                self.logger.error("Problem waiting for images: {}".format(e))

        return camera_events

    def analyze_recent(self):
        """Analyze the most recent exposure

        Compares the most recent exposure to the reference exposure and determines
        the offset between the two.

        Returns:
            dict: Offset information
        """
        # Clear the offset info
        self.current_offset_info = None

        pointing_image_id, pointing_image = self.current_observation.pointing_image
        self.logger.debug(f"Analyzing recent image using pointing image: '{pointing_image}'")

        try:
            # Get the image to compare
            image_id, image_path = self.current_observation.last_exposure

            current_image = Image(image_path, location=self.earth_location, config_port=self._config_port)

            solve_info = current_image.solve_field(skip_solved=False)

            self.logger.debug(f"Solve Info: {solve_info}")

            # Get the offset between the two
            self.current_offset_info = current_image.compute_offset(pointing_image)
            self.logger.debug(f'Offset Info: {self.current_offset_info}')

            # Store the offset information
            self.db.insert_current('offset_info', {
                'image_id': image_id,
                'd_ra': self.current_offset_info.delta_ra.value,
                'd_dec': self.current_offset_info.delta_dec.value,
                'magnitude': self.current_offset_info.magnitude.value,
                'unit': 'arcsec',
            })

        except error.SolveError:
            self.logger.warning("Can't solve field, skipping")
        except Exception as e:
            self.logger.warning(f"Problem in analyzing: {e!r}")

        return self.current_offset_info

    def update_tracking(self, **kwargs):
        """Update tracking with rate adjustment.

        The `current_offset_info` contains information about how far off
        the center of the current image is from the pointing image taken
        at the start of an observation. This offset info is given in arcseconds
        for the RA and Dec.

        A mount will accept guiding adjustments in number of milliseconds
        to move in a specified direction, where the direction is either `east/west`
        for the RA axis and `north/south` for the Dec.

        Here we take the number of arcseconds that the mount is offset and,
        via the `mount.get_ms_offset`, find the number of milliseconds we
        should adjust in a given direction, one for each axis.

        The minimum and maximum tracking corrections can be passed as keyword
        arguments (`min_tracking_threshold=100` and `max_tracking_threshold=99999`)
        or can be specified in the mount config settings.

        Args:
            **kwargs: Keyword arguments that are passed to `get_tracking_correction`
                and `correct_tracking`.
        """
        if self.current_offset_info is not None:
            self.logger.debug("Updating the tracking")

            # Get the pier side of pointing image
            _, pointing_image = self.current_observation.pointing_image
            pointing_ha = pointing_image.header_ha

            try:
                pointing_ha = pointing_ha.value
            except AttributeError:
                pass

            self.logger.debug("Pointing HA: {:.02f}".format(pointing_ha))
            correction_info = self.mount.get_tracking_correction(
                self.current_offset_info,
                pointing_ha,
                **kwargs
            )

            try:
                self.mount.correct_tracking(correction_info, **kwargs)
            except error.Timeout:
                self.logger.warning("Timeout while correcting tracking")

    def get_standard_headers(self, observation=None):
        """Get a set of standard headers

        Args:
            observation (`~pocs.scheduler.observation.Observation`, optional): The
                observation to use for header values. If None is given, use
                the `current_observation`.

        Returns:
            dict: The standard headers
        """

        if observation is None:
            observation = self.current_observation

        assert observation is not None, self.logger.warning(
            "No observation, can't get headers")

        field = observation.field

        self.logger.debug("Getting headers for : {}".format(observation))

        t0 = current_time()
        moon = get_moon(t0, self.observer.location)

        headers = {
            'airmass': self.observer.altaz(t0, field).secz.value,
            'creator': "POCSv{}".format(self.__version__),
            'elevation': self.location.get('elevation').value,
            'ha_mnt': self.observer.target_hour_angle(t0, field).value,
            'latitude': self.location.get('latitude').value,
            'longitude': self.location.get('longitude').value,
            'moon_fraction': self.observer.moon_illumination(t0),
            'moon_separation': field.coord.separation(moon).value,
            'observer': self.get_config('name', default=''),
            'origin': 'Project PANOPTES',
            'tracking_rate_ra': self.mount.tracking_rate,
        }

        # Add observation metadata
        headers.update(observation.status)

        # Explicitly convert EQUINOX to float
        try:
            equinox = float(headers['equinox'].replace('J', ''))
        except BaseException:
            equinox = 2000.  # We assume J2000

        headers['equinox'] = equinox

        return headers

    def autofocus_cameras(self, camera_list=None, **kwargs):
        """
        Perform autofocus on all cameras with focus capability, or a named subset
        of these. Optionally will perform a coarse autofocus first, otherwise will
        just fine tune focus.

        Args:
            camera_list (list, optional): list containing names of cameras to autofocus.
            **kwargs: Options passed to the underlying `Focuser.autofocus` method.

        Returns:
            dict of str:threading_Event key:value pairs, containing camera names and
                corresponding Events which will be set when the camera completes autofocus.
        """
        if camera_list:
            # Have been passed a list of camera names, extract dictionary
            # containing only cameras named in the list
            cameras = {cam_name: self.cameras[
                cam_name] for cam_name in camera_list if cam_name in self.cameras.keys()}
            if cameras == {}:
                self.logger.warning(
                    "Passed a list of camera names ({}) but no matches found".format(camera_list))
        else:
            # No cameras specified, will try to autofocus all cameras from
            # self.cameras
            cameras = self.cameras

        autofocus_events = dict()

        # Start autofocus with each camera
        for cam_name, camera in cameras.items():
            self.logger.debug("Autofocusing camera: {}".format(cam_name))

            try:
                assert camera.focuser.is_connected
            except AttributeError:
                self.logger.debug(
                    'Camera {} has no focuser, skipping autofocus'.format(cam_name))
            except AssertionError:
                self.logger.debug(
                    'Camera {} focuser not connected, skipping autofocus'.format(cam_name))
            else:
                try:
                    # Start the autofocus
                    autofocus_event = camera.autofocus(**kwargs)
                except Exception as e:
                    self.logger.error(
                        "Problem running autofocus: {}".format(e))
                else:
                    autofocus_events[cam_name] = autofocus_event

        return autofocus_events

    def open_dome(self):
        """Open the dome, if there is one.

        Returns: False if there is a problem opening the dome,
                 else True if open (or if not exists).
        """
        if not self.dome:
            return True
        if not self.dome.connect():
            return False
        if not self.dome.is_open:
            self.logger.info('Opening dome')
        return self.dome.open()

    def close_dome(self):
        """Close the dome, if there is one.

        Returns: False if there is a problem closing the dome,
                 else True if closed (or if not exists).
        """
        if not self.dome:
            return True
        if not self.dome.connect():
            return False
        if not self.dome.is_closed:
            self.logger.info('Closed dome')
        return self.dome.close()
