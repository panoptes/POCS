import glob
import os
import time

from datetime import datetime

from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_sun

from . import PanBase
from .scheduler.constraint import Duration
from .scheduler.constraint import MoonAvoidance
from .utils import current_time
from .utils import error
from .utils import list_connected_cameras
from .utils import load_module


class Observatory(PanBase):

    def __init__(self, *args, **kwargs):
        """ Main Observatory class

        Starts up the observatory. Reads config file, sets up location,
        dates, mount, cameras, and weather station

        """
        super().__init__(*args, **kwargs)

        self.logger.info('\tInitializing observatory')

        # Setup information about site location
        self.logger.info('\t\t Setting up location')
        self.earth_location = None
        self.observer = None
        self._setup_location()

        self.logger.info('\t\t Setting up mount')
        self.mount = None
        self._create_mount()

        self.logger.info('\t\t Setting up cameras')
        self.cameras = dict()
        self._primary_camera = None
        self._create_cameras(**kwargs)

        self.logger.info('\t\t Setting up scheduler')
        self.scheduler = None
        self._create_scheduler()

        self._image_dir = self.config['directories']['images']
        self.logger.info('\t Observatory initialized')

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_dark(self):
        horizon = self.location.get('twilight_horizon', -18 * u.degree)

        time = current_time()
        is_dark = self.observer.is_night(time, horizon=horizon)

        if not is_dark:
            self.logger.debug("Is dark (☉ < {}): {}".format(horizon, is_dark))
            sun_pos = self.observer.altaz(time, target=get_sun(time)).alt
            self.logger.debug("Sun position: {:.02f}".format(sun_pos))

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


##################################################################################################
# Methods
##################################################################################################

    def power_down(self):
        self.logger.debug("Shutting down observatory")
        # Stop cameras if exposing

    def status(self):
        """ Get the status for various parts of the observatory """
        status = {}
        try:
            t = current_time()
            local_time = str(datetime.now()).split('.')[0]

            if self.mount.is_initialized:
                status['mount'] = self.mount.status()

            if self.current_observation:
                status['observation'] = self.current_observation.status()

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

        except Exception as e:
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

        try:
            self.logger.debug("Getting observation for observatory")
            self.scheduler.get_observation(*args, **kwargs)
        except Exception as e:
            raise error.NoObservation("No valid observations found: {}".format(e))

        return self.current_observation

    # def observe(self):
    #     """ Make an observation for the current target.

    #     This method gets the current target's visit and takes the next
    #     exposure corresponding to the current observation.

    #     Returns:
    #         observation:    An `Observation` object.
    #     """

    #     # Get the current visit
    #     images = []
    #     images = visit.take_exposures()
    #     return images

    # def analyze_recent(self, **kwargs):
    #     """ Analyze the most recent `exposure`

    #     Converts the raw CR2 images into FITS and measures the offset. Does some
    #     bookkeeping. Information about the exposure, including the offset from the
    #     `reference_image` is returned.
    #     """
    #     target = self.current_observation
    #     self.logger.debug("For analyzing: Target: {}".format(target))

    #     observation = target.current_visit
    #     self.logger.debug("For analyzing: Observation: {}".format(observation))

    #     exposure = observation.current_exposure
    #     self.logger.debug("For analyzing: Exposure: {}".format(exposure))

    #     # Get the standard FITS headers. Includes information about target
    #     fits_headers = self._get_standard_headers(target=target)
    #     fits_headers['title'] = target.name

    #     try:
    #         kwargs = {}
    #         if 'ra_center' in target.guide_wcsinfo:
    #             kwargs['ra'] = target.guide_wcsinfo['ra_center'].value
    #         if 'dec_center' in target.guide_wcsinfo:
    #             kwargs['dec'] = target.guide_wcsinfo['dec_center'].value
    #         if 'fieldw' in target.guide_wcsinfo:
    #             kwargs['radius'] = target.guide_wcsinfo['fieldw'].value
    #         else:
    #             kwargs['radius'] = 15.0

    #         # Process the raw images (just makes a pretty right now - we solved above and offset below)
    #         self.logger.debug("Starting image processing")
    #         exposure.process_images(fits_headers=fits_headers, solve=False, **kwargs)
    #     except Exception as e:
    #         self.logger.warning("Problem analyzing: {}".format(e))

    #     self.logger.debug("Getting offset from guide")
    #     offset_info = target.get_image_offset(exposure, with_plot=True)

    #     return offset_info

    # def update_tracking(self):
    #     target = self.current_observation
    #     pass

    #     # Make sure we have a target
    #     if target.current_visit is not None:

    #         offset_info = target.offset_info

    #         ra_delta_rate = offset_info.get('ra_delta_rate', 0.0)
    #         if ra_delta_rate != 0.0:
    #             self.logger.debug("Delta RA Rate: {}".format(ra_delta_rate))
    #             self.mount.set_tracking_rate(delta=ra_delta_rate)

    #         # Get the delay for the RA and Dec and adjust mount accordingly.
    #         for direction in ['dec', 'ra']:
    #             next

    #             # Now adjust for existing offset
    #             key = '{}_ms_offset'.format(direction)
    #             self.logger.debug("{}".format(key))

    #             if key in offset_info:
    #                 self.logger.debug("Check offset values for {} {}".format(direction, target.offset_info))

    #                 # Get the offset infomation
    #                 ms_offset = offset_info.get(key, 0)
    #                 if isinstance(ms_offset, u.Quantity):
    #                     ms_offset = ms_offset.value
    #                 ms_offset = int(ms_offset)

    #                 # Only adjust a reasonable offset
    #                 self.logger.debug("Checking {} {}".format(key, ms_offset))
    #                 if abs(ms_offset) > 10.0 and abs(ms_offset) <= 5000.0:

    #                     # Add some offset to the offset
    #                     # One-fourth of time. FIXME
    #                     processing_time_delay = int(ms_offset / 4)
    #                     self.logger.debug("Processing time delay: {}".format(processing_time_delay))

    #                     ms_offset = ms_offset + processing_time_delay
    #                     self.logger.debug("Total offset: {}".format(ms_offset))

    #                     if direction == 'ra':
    #                         if ms_offset > 0:
    #                             direction_cardinal = 'west'
    #                         else:
    #                             direction_cardinal = 'east'
    #                     elif direction == 'dec':
    #                         if ms_offset > 0:
    #                             direction_cardinal = 'south'
    #                         else:
    #                             direction_cardinal = 'north'

    #                     # Now that we have direction, all ms are positive
    #                     ms_offset = abs(ms_offset)

    #                     move_dir = 'move_ms_{}'.format(direction_cardinal)
    #                     move_ms = "{:05.0f}".format(ms_offset)
    #                     self.logger.debug("Adjusting tracking by {} to direction {}".format(move_ms, move_dir))

    #                     self.mount.serial_query(move_dir, move_ms)

    #                     # The above is a non-blocking command but if we issue the next command (via the for loop)
    #                     # then it will override the above, so we manually block for one second
    #                     time.sleep(abs(ms_offset) / 1000)
    #                 else:
    #                     self.logger.debug("Offset not in range")

    #     # Reset offset_info
    #     target.offset_info = {}


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

        if 'location' in self.config:
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
            self.logger.debug("location set: {}".format(self.location))
            self.logger.debug("setting earth_location: {}".format(self.location))
            # Create an EarthLocation for the mount
            location = EarthLocation(
                lat=self.location.get('latitude'),
                lon=self.location.get('longitude'),
                height=self.location.get('elevation'),
            )
            self.earth_location = location
            self.observer = Observer(location=location, name=name, timezone=timezone)
        else:
            raise error.Error(msg='Bad site information')

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
            port = mount_info.get('port')
            driver = mount_info.get('driver')
            if len(glob.glob(port)) == 0:
                raise error.PanError(
                    msg="The mount port ({}) is not available. Use --simulator=mount for simulator. Exiting.".format(
                        port),
                    exit=True)

        self.logger.debug('Creating mount: {}'.format(model))

        module = load_module('pocs.mount.{}'.format(driver))

        try:
            # Make the mount include site information
            mount = module.Mount(location=self.earth_location)
        except ImportError:
            raise error.NotFound(msg=model)

        self.mount = mount
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

        a_simulator = 'camera' in self.config['simulator']
        if a_simulator:
            self.logger.debug("Using simulator for camera")

        ports = list()

        # Lookup the connected ports if not using a simulator
        auto_detect = kwargs.get('auto_detect', camera_info.get('auto_detect', False))
        if not a_simulator and auto_detect:
            self.logger.debug("Auto-detecting ports for cameras")
            ports = list_connected_cameras()

            if len(ports) == 0:
                raise error.PanError(msg="No cameras detected. Use --simulator=camera for simulator.", exit=True)
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
                    camera_port = camera_config['port']

            else:
                camera_model = 'simulator'
                camera_port = '/dev/camera/simulator'

            self.logger.debug('Creating camera: {}'.format(camera_model))

            try:
                module = load_module('pocs.camera.{}'.format(camera_model))
                self.logger.debug('Camera module: {}'.format(module))
            except ImportError:
                raise error.CameraNotFound(msg=camera_model)
            else:
                # Create the camera object
                cam = module.Camera(name=cam_name, model=camera_model, port=camera_port)
                self.logger.debug("Camera created: {} {}".format(cam.name, cam.uid))

                if camera_info.get('primary'):
                    self.primary_camera = cam

                self.cameras[cam_name] = cam

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

        if os.path.exists(fields_path):
            self.logger.debug('Creating scheduler: {}'.format(fields_path))

            try:
                # Load the required module
                module = load_module('pocs.scheduler.{}'.format(scheduler_type))

                # Simple constraint for now
                constraints = [MoonAvoidance(), Duration(30 * u.deg)]

                # Create the Scheduler instance
                self.scheduler = module.Scheduler(fields_path, self.observer, constraints=constraints)
                self.logger.debug("Scheduler created")
            except ImportError as e:
                raise error.NotFound(msg=e)
        else:
            self.logger.warning("Fields file does not exist: {}".format(fields_file))

    def _get_standard_headers(self, target=None):
        if target is None:
            target = self.current_observation

        self.logger.debug("For analyzing: Field: {}".format(target))

        return {
            'alt-obs': self.location.get('elevation'),
            'author': self.config.get('name', ''),
            'date-end': current_time().isot,
            'ha': self.scheduler.target_hour_angle(current_time(), target),
            'dec': target.coord.dec.value,
            'dec_nom': target.coord.dec.value,
            'epoch': float(target.coord.epoch),
            'equinox': target.coord.equinox,
            'instrument': self.config.get('name', ''),
            'lat-obs': self.location.get('latitude').value,
            'latitude': self.location.get('latitude').value,
            'long-obs': self.location.get('longitude').value,
            'longitude': self.location.get('longitude').value,
            'object': target.name,
            'observer': self.config.get('name', ''),
            'organization': 'Project PANOPTES',
            'ra': target.coord.ra.value,
            'ra_nom': target.coord.ra.value,
            'ra_obj': target.coord.ra.value,
            'telescope': self.config.get('name', ''),
            'title': target.name,
        }


##################################################################################################
# Private Utility Methods
##################################################################################################

    def _track_target(self, target, hours=2.0):
        """ Track a target for set amount of time.

        This is a utility method that will track a given `target` for a certain number of `hours`.

        WARNING:
            This is a blocking method! It is a utility method only.

        Args:
            target(SkyCoord):   An astropy.coordinates.SkyCoord.
            hours(float):       Number of hours to track for.
        """
        self.logger.info("Tracking target {} for {} hours".format(target, hours))

        self.mount.set_target_coordinates(target)
        self.mount.slew_to_target()

        self.logger.info("Slewing to {}".format(target))
        while self.mount.is_slewing:
            time.sleep(5)

        self.logger.info("Tracking target. Sleeping for {} hours".format(hours))
        time.sleep(hours * 60 * 60)
        self.logger.info("I just finished tracking {}".format(target))
