import os
import time

from collections import OrderedDict
from datetime import datetime

from glob import glob

from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_moon
from astropy.coordinates import get_sun
from astropy.io import fits
from astropy.stats import sigma_clipped_stats

from . import PanBase
from .guide.bisque import Guide
from .images import Image
from .scheduler.constraint import Duration
from .scheduler.constraint import MoonAvoidance
from .scheduler.observation import DitheredObservation
from .scheduler.observation import Field
from .utils import altaz_to_radec
from .utils import current_time
from .utils import error
from .utils import flatten_time
from .utils import hdr
from .utils import images as img_utils
from .utils import list_connected_cameras
from .utils import load_module


class Observatory(PanBase):

    def __init__(self, *args, **kwargs):
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

        self.logger.info('\tSetting up cameras')
        self.cameras = OrderedDict()
        self._primary_camera = None
        self._create_cameras(**kwargs)

        self.logger.info('\tSetting up scheduler')
        self.scheduler = None
        self._create_scheduler()

        self._has_hdr_mode = kwargs.get('with_hdr_mode', self.config['cameras'].get('hdr_mode', False))
        self._has_autoguider = kwargs.get('with_autoguider', 'guider' in self.config)

        # Creating an imager array object
        if self.has_hdr_mode:
            self.logger.info('\tSetting up HDR imager array')
            self.imager_array = hdr.create_imager_array()

        if self.has_autoguider:
            self.logger.info("\tSetting up autoguider")
            try:
                self._create_autoguider()
            except Exception as e:
                self._has_autoguider = False
                self.logger.warning("Problem setting autoguider, continuing without: {}".format(e))

        self.offset_info = None

        self._image_dir = self.config['directories']['images']
        self.logger.info('\t Observatory initialized')

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_dark(self):
        horizon = self.location.get('twilight_horizon', -18 * u.degree)

        t0 = current_time()
        is_dark = self.observer.is_night(t0, horizon=horizon)

        if not is_dark:
            sun_pos = self.observer.altaz(t0, target=get_sun(t0)).alt
            self.logger.debug("Sun {:.02f} > {}".format(sun_pos, horizon))

        return is_dark

    @property
    def sidereal_time(self):
        return self.observer.local_sidereal_time(current_time())

    @property
    def primary_camera(self):
        return self._primary_camera

    @primary_camera.setter
    def primary_camera(self, cam):
        cam.is_primary = True
        self._primary_camera = cam

    @property
    def current_observation(self):
        return self.scheduler.current_observation

    @current_observation.setter
    def current_observation(self, new_observation):
        self.scheduler.current_observation = new_observation

    @property
    def has_hdr_mode(self):
        """ Does camera support HDR mode

        Returns:
            bool: HDR enabled, default False
        """
        return self._has_hdr_mode

    @property
    def has_autoguider(self):
        """ Does camera have attached autoguider

        Returns:
            bool: True if has autoguider
        """
        return self._has_autoguider

##################################################################################################
# Methods
##################################################################################################

    def power_down(self):
        """Power down the observatory. Currently does nothing
        """
        self.logger.debug("Shutting down observatory")
        if self.mount.is_initialized:
            self.mount.disconnect()

    def status(self):
        """Get status information for various parts of the observatory
        """
        status = {}
        try:
            t = current_time()
            local_time = str(datetime.now()).split('.')[0]

            if self.mount.is_initialized:
                status['mount'] = self.mount.status()
                status['mount']['current_ha'] = self.observer.target_hour_angle(
                    t, self.mount.get_current_coordinates())
                if self.mount.has_target:
                    status['mount']['mount_target_ha'] = self.observer.target_hour_angle(
                        t, self.mount.get_target_coordinates())
        except Exception as e:  # pragma: no cover
            self.logger.warning("Can't get mount status from observatory: {}".format(e))

        try:
            if self.current_observation:
                status['observation'] = self.current_observation.status()
                status['observation']['field_ha'] = self.observer.target_hour_angle(
                    t, self.current_observation.field)
        except Exception as e:  # pragma: no cover
            self.logger.warning("Can't get observation status from observatory: {}".format(e))

        try:
            status['observer'] = {
                'siderealtime': str(self.sidereal_time),
                'utctime': t,
                'localtime': local_time,
                'local_evening_astro_time': self.observer.twilight_evening_astronomical(t, which='next'),
                'local_morning_astro_time': self.observer.twilight_morning_astronomical(t, which='next'),
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
        self.scheduler.get_observation(*args, **kwargs)

        if self.scheduler.current_observation is None:
            raise error.NoObservation("No valid observations found")

        return self.current_observation

    def cleanup_observations(self):
        """Cleanup observation list
        Loops through the `observed_list` performing cleanup taskts. Resets
        `observed_list` when done
        """
        for seq_time, observation in self.scheduler.observed_list.items():
            self.logger.debug("Housekeeping for {}".format(observation))

            try:
                dir_name = os.path.join(
                    self.config['directories']['images'],
                    observation.field.field_name,
                    self.primary_camera.uid,
                    observation.seq_time
                )

                # Remove .solved files
                self.logger.debug('Removing .solved files')
                for f in glob('{}/*.solved'.format(dir_name)):
                    try:
                        os.remove(f)
                    except OSError as e:
                        self.logger.warning('Could not delete file: {}'.format(e))

                jpg_list = glob('{}/*.jpg'.format(dir_name))

                if len(jpg_list) == 0:
                    continue

                # Create timelapse
                self.logger.debug('Creating timelapse for {}'.format(dir_name))
                video_file = img_utils.create_timelapse(dir_name)
                self.logger.debug('Timelapse created: {}'.format(video_file))

                # Remove jpgs
                self.logger.debug('Removing jpgs')
                for f in jpg_list:
                    try:
                        os.remove(f)
                    except OSError as e:
                        self.logger.warning('Could not delete file: {}'.format(e))

            except Exception as e:
                self.logger.warning('Problem with cleanup:'.format(e))

            self.logger.debug('Cleanup for {} finished'.format(observation))

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

        # List of camera events to wait for to signal exposure is done processing
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

    def finish_observing(self):
        """Performs various cleanup functions for observe
        Extracts the most recent observation metadata from the mongo `current` collection
        and increments the exposure count for the `current_observation`
        """

        # Lookup the current observation
        image_info = self.db.get_current('observations')
        image_id = image_info['data']['image_id']
        file_path = image_info['data']['file_path']

        # Add most recent exposure to list
        self.current_observation.exposure_list[image_id] = file_path

    def slew_to_target(self):
        """ Slew to target and turn on guiding

        This is convenience method to slew to the target and turn on the guiding
        given a large spearation

        """
        separation_limit = 0.5 * u.degree

        if self.has_autoguider and self.autoguider.is_guiding:
            try:
                self.autoguider.stop_guiding()
            except Exception as e:
                self.logger.warning("Problem stopping autoguide")

        # Slew to target
        self.mount.slew_to_target()

        self.status()  # Send status update and update `is_tracking`

        # WARNING: Some kind of timeout needed
        while not self.mount.is_tracking and self.mount.distance_from_target() >= separation_limit:
            self.logger.debug("Slewing to target")
            time.sleep(1)

        # Turn on autoguiding
        if self.has_autoguider:
            try:
                self.autoguider.autoguide()
            except error.PanError:
                self.logger.warning("Continuing without guiding")

    def analyze_recent(self):
        """Analyze the most recent exposure
        Compares the most recent exposure to the reference exposure and determines
        the offset between the two.
        Returns:
            dict: Offset information
        """
        # Clear the offset info
        self.offset_info = dict()

        ref_image_id, ref_image_path = self.current_observation.first_exposure

        try:
            # If we just finished the first exposure, solve the image so it can be reference
            if self.current_observation.current_exp == 1:
                ref_image = Image(ref_image_path)
                ref_solve_info = ref_image.solve_field()

                try:
                    del ref_solve_info['COMMENT']
                except KeyError:
                    pass

                try:
                    del ref_solve_info['HISTORY']
                except KeyError:
                    pass

                self.logger.debug("Reference Solve Info: {}".format(ref_solve_info))
            else:
                # Get the image to compare
                image_id, image_path = self.current_observation.last_exposure

                current_image = Image(image_path, wcs_file=ref_image_path)
                solve_info = current_image.solve_field()

                try:
                    del solve_info['COMMENT']
                except KeyError:
                    pass

                try:
                    del solve_info['HISTORY']
                except KeyError:
                    pass

                self.logger.debug("Solve Info: {}".format(solve_info))

                # Get the offset between the two
                self.offset_info = current_image.compute_offset(ref_image_path)
                self.logger.debug('Offset Info: {}'.format(self.offset_info))

                # Update the observation info with the offsets
                self.db.observations.update({'image_id': image_id}, {
                    '$set': {
                        'offset_info': self.offset_info,
                    },
                })

                # Compress the image
                # self.logger.debug("Compressing image")
                # img_utils.fpack(image_path)
        except error.SolveError:
            self.logger.warning("Can't solve field, skipping")
        except Exception as e:
            self.logger.warning("Problem in analyzing: {}".format(e))

        # Increment the exposure count
        self.current_observation.current_exp += 1

        return self.offset_info

    def update_tracking(self):
        """Update tracking with rate adjustment
        Uses the `rate_adjustment` key from the `self.offset_info`
        """
        pass

    def get_standard_headers(self, observation=None):
        """Get a set of standard headers
        Args:
            observation (`~pocs.scheduler.observation.Observation`, optional): The
                observation to use for header values. If None is given, use the `current_observation`
        Returns:
            dict: The standard headers
        """
        if observation is None:
            observation = self.current_observation

        assert observation is not None, self.logger.warning("No observation, can't get headers")

        field = observation.field

        self.logger.debug("Getting headers for : {}".format(observation))

        time = current_time()
        moon = get_moon(time, self.observer.location)

        headers = {
            'airmass': self.observer.altaz(time, field).secz.value,
            'creator': "POCSv{}".format(self.__version__),
            'elevation': self.location.get('elevation').value,
            'ha_mnt': self.observer.target_hour_angle(time, field).value,
            'latitude': self.location.get('latitude').value,
            'longitude': self.location.get('longitude').value,
            'moon_fraction': self.observer.moon_illumination(time),
            'moon_separation': field.coord.separation(moon).value,
            'observer': self.config.get('name', ''),
            'origin': 'Project PANOPTES',
            'tracking_rate_ra': self.mount.tracking_rate,
        }

        # Add observation metadata
        headers.update(observation.status())

        return headers

    def take_evening_flats(self, alt=None, az=None, min_counts=5000, max_counts=15000, bias=1000, max_exptime=60.):
        """ Take flat fields

        Args:
            alt (float, optional): Altitude for flats
            az (float, optional): Azimuth for flats
            min_counts (int, optional): Minimum ADU count
            max_counts (int, optional): Maximum ADU count
            bias (int, optional): Default bias for the cameras
            max_exptime (float, optional): Maximum exposure time before stopping

        """
        flat_config = self.config['flat_field']['twilight']

        if alt is None:
            alt = flat_config['alt']

        if az is None:
            az = flat_config['az']

        flat_coords = altaz_to_radec(alt=alt, az=az, location=self.earth_location, obstime=current_time())

        self.logger.debug("Creating dithered observation")
        field = Field('Evening Flats', flat_coords.to_string('hmsdms'))
        flat_obs = DitheredObservation(field, exp_time=1. * u.second)
        flat_obs.seq_time = current_time(flatten=True)

        # TODO: Get the dither coordinates and assign here

        self.logger.debug("Flat-field observation: {}".format(flat_obs))
        target_adu = 0.5 * (min_counts + max_counts)

        exp_times = {cam_name: 1. * u.second for cam_name in self.cameras.keys()}

        # Get the filename
        image_dir = "{}/fields/".format(self.config['directories']['images'], )

        # Loop until conditions are met for flat-fielding
        while True:
            self.logger.debug("Slewing to flat-field coords: {}".format(flat_obs.field))
            self.mount.set_target_coordinates(flat_obs.field)
            self.mount.slew_to_target()

            while not self.mount.is_tracking:
                self.logger.debug("Slewing to target")
                time.sleep(0.5)

            start_time = current_time()

            fits_headers = self.get_standard_headers(observation=flat_obs)
            fits_headers['start_time'] = flatten_time(start_time)  # Common start time for cameras

            camera_events = dict()

            for cam_name, camera in self.cameras.items():

                filename = "{}/flats/{}/{}/{}.{}".format(
                    image_dir,
                    camera.uid,
                    flat_obs.seq_time,
                    'flat_{:02d}'.format(flat_obs.current_exp),
                    camera.file_extension)

                # Take picture and wait for result
                camera_event = camera.take_observation(
                    flat_obs, fits_headers, filename=filename, exp_time=exp_times[cam_name])

                camera_events[cam_name] = {
                    'event': camera_event,
                    'filename': filename,
                }

            # Will block here until done exposing on all cameras
            while not all([info['event'].is_set() for info in camera_events.values()]):
                self.logger.debug('Waiting for flat-field image')
                time.sleep(1)

            # Check the counts for each image
            for cam_name, info in camera_events.items():
                img_file = info['filename']
                self.logger.debug("Checking counts for {}".format(img_file))

                data = fits.getdata(img_file)

                mean, median, stddev = sigma_clipped_stats(data)

                counts = mean - bias
                if counts <= 0:  # This is in the original DragonFly code so copying
                    counts = 10

                self.logger.debug("Counts: {}".format(counts))
                if counts < min_counts or counts > max_counts:
                    self.logger.debug("Counts outside min/max range, should be discarded")

                elapsed_time = (current_time() - start_time).sec
                self.logger.debug("Elapsed time: {}".format(elapsed_time))

                # Round up to the nearest second
                exp_time = int(exp_times[cam_name] * (target_adu / counts) * (2.0 ** (elapsed_time / 180.0)) + 0.5)
                self.logger.debug("Suggested exp_time for {}: {}".format(cam_name, exp_time))
                exp_times[cam_name] = exp_time * u.second

            if any([t >= max_exptime for t in exp_times.values()]):
                self.logger.debug("Exposure times greater than max, stopping flat fields")
                break

            flat_obs.current_exp += 1

    def autofocus_cameras(self, camera_list=None, coarse=False):
        """
        Perform autofocus on all cameras with focus capability, or a named subset of these. Optionally will
        perform a coarse autofocus first, otherwise will just fine tune focus.

        Args:
            camera_list (list, optional): list containing names of cameras to autofocus.
            coarse (bool, optional): Whether to performan a coarse autofocus before fine tuning, default False

        Returns:
            dict of str:threading_Event key:value pairs, containing camera names and corresponding Events which
                will be set when the camera completes autofocus
        """
        if camera_list:
            # Have been passed a list of camera names, extract dictionary containing only cameras named in the list
            cameras = {cam_name: self.cameras[cam_name] for cam_name in camera_list if cam_name in self.cameras.keys()}
            if cameras == {}:
                self.logger.warning("Passed a list of camera names ({}) but no matches found".format(camera_list))
        else:
            # No cameras specified, will try to autofocus all cameras from self.cameras
            cameras = self.cameras

        autofocus_events = dict()

        # Start autofocus with each camera
        for cam_name, camera in cameras.items():
            self.logger.debug("Autofocusing camera: {}".format(cam_name))

            try:
                assert camera.focuser.is_connected
            except AttributeError:
                self.logger.debug('Camera {} has no focuser, skipping autofocus'.format(cam_name))
            except AssertionError:
                self.logger.debug('Camera {} focuser not connected, skipping autofocus'.format(cam_name))
            else:
                try:
                    # Start the autofocus
                    autofocus_event = camera.autofocus(coarse=coarse)
                except Exception as e:
                    self.logger.error("Problem running autofocus: {}".format(e))
                else:
                    autofocus_events[cam_name] = autofocus_event

        return autofocus_events

##################################################################################################
# Private Methods
##################################################################################################

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
            utc_offset = config_site.get('utc_offset')

            pressure = config_site.get('pressure', 0.680) * u.bar
            elevation = config_site.get('elevation', 0 * u.meter)
            horizon = config_site.get('horizon', 30 * u.degree)
            twilight_horizon = config_site.get('twilight_horizon', -18 * u.degree)

            self.location = {
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'elevation': elevation,
                'timezone': timezone,
                'utc_offset': utc_offset,
                'pressure': pressure,
                'horizon': horizon,
                'twilight_horizon': twilight_horizon,
            }
            self.logger.debug("Location: {}".format(self.location))

            # Create an EarthLocation for the mount
            self.earth_location = EarthLocation(lat=latitude, lon=longitude, height=elevation)
            self.observer = Observer(location=self.earth_location, name=name, timezone=timezone)
        except Exception:
            raise error.PanError(msg='Bad site information')

    def _create_mount(self, mount_info=None):
        """Creates a mount object.
        Details for the creation of the mount object are held in the
        configuration file or can be passed to the method.
        This method ensures that the proper mount type is loaded.
        Note:
            This does not actually make a serial connection to the mount. To do so,
            call the 'mount.connect()' explicitly.
        Args:
            mount_info (dict):  Configuration items for the mount.
        Returns:
            pocs.mount:     Returns a sub-class of the mount type
        """
        if mount_info is None:
            mount_info = self.config.get('mount')

        model = mount_info.get('model')
        port = mount_info.get('port')

        if 'mount' in self.config.get('simulator', []):
            model = 'simulator'
            driver = 'simulator'
            mount_info['simulator'] = True
        else:
            model = mount_info.get('brand')
            driver = mount_info.get('driver')

            if model != 'bisque':
                port = mount_info.get('port')
                if port is None or len(glob(port)) == 0:
                    msg = "Mount port ({}) not available. Use --simulator=mount for simulator. Exiting.".format(port)
                    raise error.PanError(msg=msg, exit=True)

        self.logger.debug('Creating mount: {}'.format(model))

        module = load_module('pocs.mount.{}'.format(driver))

        # Make the mount include site information
        self.mount = module.Mount(location=self.earth_location)
        self.logger.debug('Mount created')

    def _create_cameras(self, **kwargs):
        """Creates a camera object(s)
        Loads the cameras via the configuration.
        Creates a camera for each camera item listed in the config. Ensures the
        appropriate camera module is loaded.
        Note: We are currently only operating with one camera and the `take_pic.sh`
            script automatically discovers the ports.
        Note:
            This does not actually make a usb connection to the camera. To do so,
            call the 'camear.connect()' explicitly.
        Args:
            **kwargs (dict): Can pass a camera_config object that overrides the info in
                the configuration file. Can also pass `auto_detect`(bool) to try and
                automatically discover the ports.
        Returns:
            list: A list of created camera objects.
        Raises:
            error.CameraNotFound: Description
            error.PanError: Description
        """
        if kwargs.get('camera_info') is None:
            camera_info = self.config.get('cameras')

        self.logger.debug("Camera config: \n {}".format(camera_info))

        a_simulator = 'camera' in self.config.get('simulator', [])
        if a_simulator:
            self.logger.debug("Using simulator for camera")

        ports = list()

        # Lookup the connected ports if not using a simulator
        auto_detect = kwargs.get('auto_detect', camera_info.get('auto_detect', False))
        if not a_simulator and auto_detect:
            self.logger.debug("Auto-detecting ports for cameras")
            try:
                ports = list_connected_cameras()
            except Exception as e:
                self.logger.warning(e)

            if len(ports) == 0:
                raise error.PanError(msg="No cameras detected. Use --simulator=camera for simulator.")
            else:
                self.logger.debug("Detected Ports: {}".format(ports))

        for cam_num, camera_config in enumerate(camera_info.get('devices', [])):
            cam_name = 'Cam{:02d}'.format(cam_num)

            if not a_simulator:
                camera_model = camera_config.get('model')

                # Assign an auto-detected port. If none are left, skip
                if auto_detect:
                    try:
                        camera_port = ports.pop()
                    except IndexError:
                        self.logger.warning("No ports left for {}, skipping.".format(cam_name))
                        continue
                else:
                    try:
                        camera_port = camera_config['port']
                    except KeyError:
                        raise error.CameraNotFound(msg="No port specified and auto_detect=False")

                camera_focuser = camera_config.get('focuser', None)

            else:
                # Set up a simulated camera with fully configured simulated focuser
                camera_model = 'simulator'
                camera_port = '/dev/camera/simulator'
                camera_focuser = {'model': 'simulator',
                                  'focus_port': '/dev/ttyFAKE',
                                  'initial_position': 20000,
                                  'autofocus_range': (40, 80),
                                  'autofocus_step': (10, 20),
                                  'autofocus_seconds': 0.1,
                                  'autofocus_size': 500}

            camera_set_point = camera_config.get('set_point', None)
            camera_filter = camera_config.get('filter_type', None)

            self.logger.debug('Creating camera: {}'.format(camera_model))

            try:
                module = load_module('pocs.camera.{}'.format(camera_model))
                self.logger.debug('Camera module: {}'.format(module))
            except ImportError:
                raise error.CameraNotFound(msg=camera_model)
            else:
                # Create the camera object
                cam = module.Camera(name=cam_name,
                                    model=camera_model,
                                    port=camera_port,
                                    set_point=camera_set_point,
                                    filter_type=camera_filter,
                                    focuser=camera_focuser)

                is_primary = ''
                if camera_info.get('primary', '') == cam.uid:
                    self.primary_camera = cam
                    is_primary = ' [Primary]'

                self.logger.debug("Camera created: {} {} {}".format(cam.name, cam.uid, is_primary))

                self.cameras[cam_name] = cam

        # If no camera was specified as primary use the first
        if self.primary_camera is None:
            self.primary_camera = self.cameras['Cam00']

        if len(self.cameras) == 0:
            raise error.CameraNotFound(msg="No cameras available. Exiting.", exit=True)

        self.logger.debug("Cameras created")

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        scheduler_config = self.config.get('scheduler', {})
        scheduler_type = scheduler_config.get('type', 'dispatch')

        # Read the targets from the file
        fields_file = scheduler_config.get('fields_file', 'simple.yaml')
        fields_path = os.path.join(self.config['directories']['targets'], fields_file)
        self.logger.debug('Creating scheduler: {}'.format(fields_path))

        if os.path.exists(fields_path):

            try:
                # Load the required module
                module = load_module('pocs.scheduler.{}'.format(scheduler_type))

                # Simple constraint for now
                constraints = [MoonAvoidance(), Duration(30 * u.deg)]

                # Create the Scheduler instance
                self.scheduler = module.Scheduler(self.observer, fields_file=fields_path, constraints=constraints)
                self.logger.debug("Scheduler created")
            except ImportError as e:
                raise error.NotFound(msg=e)
        else:
            raise error.NotFound(msg="Fields file does not exist: {}".format(fields_file))

    def _create_autoguider(self):
        guider_config = self.config['guider']
        guider = Guide(**guider_config)

        self.autoguider = guider
