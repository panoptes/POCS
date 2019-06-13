import os
import subprocess
from collections import OrderedDict
from datetime import datetime
from glob import glob

from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_moon
from astropy.coordinates import get_sun

from pocs.base import PanBase
from pocs.camera import AbstractCamera
from pocs.images import Image
from pocs.utils import current_time
from pocs.utils import error
from pocs.utils import load_module


class Observatory(PanBase):

    def __init__(self, cameras=None, scheduler=None, dome=None, *args, **kwargs):
        """Main Observatory class

        Starts up the observatory. Reads config file, sets up location,
        dates, mount, cameras, and weather station
        """
        super().__init__(*args, **kwargs)
        self.logger.info('Initializing observatory')

        # Setup information about site location
        self.logger.info('\tSetting up location')
        self.location = None
        self.earth_location = None
        self.observer = None
        self._setup_location()

        self.logger.info('\tSetting up mount')
        self.mount = None
        self._create_mount()

        self.cameras = OrderedDict()

        if cameras:
            self.logger.info('Adding the cameras to the observatory: {}', cameras)
            self._primary_camera = None
            for cam_name, camera in cameras.items():
                self.add_camera(cam_name, camera)

        # TODO(jamessynge): Discuss with Wilfred the serial port validation behavior
        # here compared to that for the mount.
        self.dome = dome

        self.logger.info('\tSetting up scheduler')
        self.scheduler = scheduler

        self.current_offset_info = None

        self._image_dir = self.config['directories']['images']
        self.logger.info('\t Observatory initialized')

##########################################################################
# Helper methods
##########################################################################

    def is_dark(self, horizon='observe', at_time=None):
        """If sun is below horizon.

        Args:
            horizon (str, optional): Which horizon to use, 'flat', 'focus', or
                'observe' (default).
            at_time (None or `astropy.time.Time`, optional): Time at which to
                check if dark, defaults to now.
        """
        if at_time is None:
            at_time = current_time()
        try:
            horizon_deg = self.config['location']['{}_horizon'.format(horizon)]
        except KeyError:
            self.logger.info(f"Can't find {horizon}_horizon, using -18°")
            horizon_deg = -18 * u.degree
        is_dark = self.observer.is_night(at_time, horizon=horizon_deg)

        if not is_dark:
            sun_pos = self.observer.altaz(at_time, target=get_sun(at_time)).alt
            self.logger.debug(f"Sun {sun_pos:.02f} > {horizon_deg} [{horizon}]")

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

        If any of the above are not present then a log message is generated and the property returns False.

        Returns:
            bool: True if observations are possible, False otherwise.
        """
        can_observe = True
        if can_observe and self.scheduler is None:
            self.logger.info(f'Scheduler not present, cannot observe.')
            can_observe = False
        if can_observe and not self.has_cameras:
            self.logger.info(f'Cameras not present, cannot observe.')
            can_observe = False
        if can_observe and self.mount is None:
            self.logger.info(f'Mount not present, cannot observe.')
            can_observe = False

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
        self.logger.debug('Adding {}: {}'.format(cam_name, camera))
        if cam_name in self.cameras:
            self.logger.debug(
                '{} already exists, replacing existing camera under that name.',
                cam_name)

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
        self.mount.disconnect()
        if self.dome:
            self.dome.disconnect()

    def status(self):
        """Get status information for various parts of the observatory
        """
        status = {}
        try:

            status['can_observe'] = self.can_observe

            t = current_time()
            local_time = str(datetime.now()).split('.')[0]

            if self.mount.is_initialized:
                status['mount'] = self.mount.status()
                status['mount']['current_ha'] = self.observer.target_hour_angle(
                    t, self.mount.get_current_coordinates())
                if self.mount.has_target:
                    status['mount']['mount_target_ha'] = self.observer.target_hour_angle(
                        t, self.mount.get_target_coordinates())

            if self.dome:
                status['dome'] = self.dome.status

            if self.current_observation:
                status['observation'] = self.current_observation.status()
                status['observation']['field_ha'] = self.observer.target_hour_angle(
                    t, self.current_observation.field)

            evening_astro_time = self.observer.twilight_evening_astronomical(t, which='next')
            morning_astro_time = self.observer.twilight_morning_astronomical(t, which='next')

            status['observer'] = {
                'siderealtime': str(self.sidereal_time),
                'utctime': t,
                'localtime': local_time,
                'local_evening_astro_time': evening_astro_time,
                'local_morning_astro_time': morning_astro_time,
                'local_sun_set_time': self.observer.sun_set_time(t),
                'local_sun_rise_time': self.observer.sun_rise_time(t),
                'local_moon_alt': self.observer.moon_altaz(t).alt,
                'local_moon_illumination': self.observer.moon_illumination(t),
                'local_moon_phase': self.observer.moon_phase(t),
            }

        except Exception as e:  # pragma: no cover
            self.logger.warning("Can't get observatory status: {}".format(e))

        return status

    def get_observation(self, *args, **kwargs):
        """Gets the next observation from the scheduler

        Returns:
            observation (pocs.scheduler.observation.Observation or None): An
                an object that represents the obervation to be made

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
            self.config['scheduler'].get('check_file', False)
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
            try:
                upload_images = self.config.get('panoptes_network', {})['image_storage']
            except KeyError:
                upload_images = False

        if make_timelapse is None:
            try:
                make_timelapse = self.config['observations']['make_timelapse']
            except KeyError:
                make_timelapse = True

        if keep_jpgs is None:
            try:
                keep_jpgs = self.config['observations']['keep_jpgs']
            except KeyError:
                keep_jpgs = True

        process_script = 'upload_image_dir.py'
        process_script_path = os.path.join(os.environ['POCS'], 'scripts', process_script)

        if self.scheduler is None:
            self.logger.info(f'Scheduler not present, cannot finish cleanup.')
            return

        for seq_time, observation in self.scheduler.observed_list.items():
            self.logger.debug("Housekeeping for {}".format(observation))

            observation_dir = os.path.join(
                self.config['directories']['images'],
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
                    process_cmd.append('--make_timelapse')

                if keep_jpgs is False:
                    process_cmd.append('--remove_jpgs')

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
                except subprocess.TimeoutExpired:  # pragma: no cover
                    clean_proc.kill()
                    outs, errs = clean_proc.communicate(timeout=10)
                    if errs is not None:
                        self.logger.warning("Problem cleaning: {}".format(errs))

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
        self.logger.debug(
            "Analyzing recent image using pointing image: '{}'".format(pointing_image))

        try:
            # Get the image to compare
            image_id, image_path = self.current_observation.last_exposure

            current_image = Image(image_path, location=self.earth_location)

            solve_info = current_image.solve_field(skip_solved=False)

            self.logger.debug("Solve Info: {}".format(solve_info))

            # Get the offset between the two
            self.current_offset_info = current_image.compute_offset(pointing_image)
            self.logger.debug('Offset Info: {}'.format(self.current_offset_info))

            # Store the offset information
            self.db.insert('offset_info', {
                'image_id': image_id,
                'd_ra': self.current_offset_info.delta_ra.value,
                'd_dec': self.current_offset_info.delta_dec.value,
                'magnitude': self.current_offset_info.magnitude.value,
                'unit': 'arcsec',
            })

        except error.SolveError:
            self.logger.warning("Can't solve field, skipping")
        except Exception as e:
            self.logger.warning("Problem in analyzing: {}".format(e))

        return self.current_offset_info

    def update_tracking(self):
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
                pointing_ha
            )

            try:
                self.mount.correct_tracking(correction_info)
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
            'observer': self.config.get('name', ''),
            'origin': 'Project PANOPTES',
            'tracking_rate_ra': self.mount.tracking_rate,
        }

        # Add observation metadata
        headers.update(observation.status())

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

##########################################################################
# Private Methods
##########################################################################

    def _setup_location(self):
        """
        Sets up the site and location details for the observatory

        Note:
            These items are read from the 'site' config directive and include:
                * name
                * latitude
                * longitude
                * timezone
                * presseure
                * elevation
                * horizon

        """
        self.logger.debug('Setting up site details of observatory')

        try:
            config_site = self.config.get('location')

            name = config_site.get('name', 'Nameless Location')

            latitude = config_site.get('latitude')
            longitude = config_site.get('longitude')

            timezone = config_site.get('timezone')

            pressure = config_site.get('pressure', 0.680) * u.bar
            elevation = config_site.get('elevation', 0 * u.meter)
            horizon = config_site.get('horizon', 30 * u.degree)
            flat_horizon = config_site.get('flat_horizon', -6 * u.degree)
            focus_horizon = config_site.get('focus_horizon', -12 * u.degree)
            observe_horizon = config_site.get('observe_horizon', -18 * u.degree)

            self.location = {
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'elevation': elevation,
                'timezone': timezone,
                'pressure': pressure,
                'horizon': horizon,
                'flat_horizon': flat_horizon,
                'focus_horizon': focus_horizon,
                'observe_horizon': observe_horizon,
            }
            self.logger.debug("Location: {}".format(self.location))

            # Create an EarthLocation for the mount
            self.earth_location = EarthLocation(
                lat=latitude, lon=longitude, height=elevation)
            self.observer = Observer(
                location=self.earth_location, name=name, timezone=timezone)
        except Exception:
            raise error.PanError(msg='Bad site information')

    def _create_mount(self, mount_info=None):
        """Creates a mount object.

        Details for the creation of the mount object are held in the
        configuration file or can be passed to the method.

        This method ensures that the proper mount type is loaded.

        Args:
            mount_info (dict):  Configuration items for the mount.

        Returns:
            pocs.mount:     Returns a sub-class of the mount type
        """
        if mount_info is None:
            mount_info = self.config.get('mount')

        model = mount_info.get('model')

        if 'mount' in self.config.get('simulator', []):
            model = 'simulator'
            driver = 'simulator'
            mount_info['simulator'] = True
        else:
            model = mount_info.get('brand')
            driver = mount_info.get('driver')

            # See if we have a serial connection
            try:
                port = mount_info['serial']['port']
                if port is None or len(glob(port)) == 0:
                    msg = "Mount port({}) not available. ".format(port) \
                        + "Use simulator = mount for simulator. Exiting."
                    raise error.MountNotFound(msg=msg)
            except KeyError:
                # TODO(jamessynge): We should move the driver specific validation into the driver
                # module (e.g. module.create_mount_from_config). This means we have to adjust the
                # definition of this method to return a validated but not fully initialized mount
                # driver.
                if model != 'bisque':
                    msg = "No port specified for mount in config file. " \
                        + "Use simulator = mount for simulator. Exiting."
                    raise error.MountNotFound(msg=msg)

        self.logger.debug('Creating mount: {}'.format(model))

        module = load_module('pocs.mount.{}'.format(driver))

        # Make the mount include site information
        self.mount = module.Mount(location=self.earth_location)

        self.logger.debug('Mount created')
