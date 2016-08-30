import glob
import os
import subprocess
import time

from datetime import datetime

from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_moon
from astropy.coordinates import get_sun

from . import PanBase
from .scheduler.constraint import Duration
from .scheduler.constraint import MoonAvoidance
from .utils import current_time
from .utils import error
from .utils import list_connected_cameras
from .utils import load_module
from .utils.images.conversions import cr2_to_fits


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
        self.location = None
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

    def status(self):
        """ Get the status for various parts of the observatory """
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

            if self.current_observation:
                status['observation'] = self.current_observation.status()
                status['observation']['field_ha'] = self.observer.target_hour_angle(
                    t, self.current_observation.field)

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

    def observe(self):
        """ Take individual images for the current observation

        This method gets the current observation and takes the next
        exposure corresponding. The CR2 is then converted to a FITS file
        with all appropriate metadata written to both a mongo instance
        and to the FITS file for each exposure.

        """
        image_dir = self.config['directories']['images']
        start_time = current_time(flatten=True)

        procs = list()  # Store subprocesses
        metadata_info = dict()  # Store metadata about each exposure

        # Get observatory metadata
        headers = self.get_standard_headers()

        # Add observation metadata
        headers.update(self.current_observation.status())

        # Take exposure with each camera
        for cam_name, camera in self.cameras.items():
            self.logger.debug("Exposing for camera: {}".format(cam_name))

            filename = "{}/{}/{}/{}.cr2".format(
                self.current_observation.field.field_name,
                camera.uid,
                self.current_observation.seq_time,
                start_time)

            file_path = "{}/fields/{}".format(image_dir, filename)

            image_id = '{}_{}_{}'.format(
                self.config['name'],
                camera.uid,
                self.current_observation.seq_time
            )
            self.logger.debug("image_id: {}".format(image_id))

            # Take pointing picture and wait for result
            try:
                proc = camera.take_exposure(seconds=self.current_observation.exp_time, filename=file_path)
                self.logger.debug("Image: PID {} File {}".format(proc.pid, filename))
                procs.append(proc)
            except Exception as e:
                self.logger.error("Problem waiting for images: {}".format(e))
            else:

                # Camera metadata
                metadata_info[image_id] = {
                    'camera_uid': camera.uid,
                    'camera_name': cam_name,
                    'filter': camera.filter_type,
                    'img_file': filename,
                    'is_primary': camera.is_primary,
                    'start_time': start_time,
                    'iamge_id': image_id,
                    'sequence_id': '{}_{}_{}'.format(
                        self.config['name'],
                        camera.uid,
                        self.current_observation.seq_time
                    ),
                }

                # Add header metadata to metadata for each camera
                metadata_info[image_id].update(headers)

        # Wait for the exposures (BLOCKING)
        for proc in procs:
            try:
                proc.wait(timeout=1.5 * self.current_observation.exp_time.value)
            except subprocess.TimeoutExpired:
                self.logger.debug("Still waiting for camera")
                proc.kill()

        # Add each cameras metadata to db
        for image_id, info in metadata_info.items():
            file_path = "{}/fields/{}".format(image_dir, info['img_file'])

            self.logger.debug("Converting CR2 -> FITS: {}".format(file_path))
            fits_path = cr2_to_fits(file_path, headers=info)

            info['fits_path'] = fits_path

            self.logger.debug("Adding image metadata to db: {}".format(image_id))
            self.db.observations.insert_one({
                'data': info,
                'date': current_time(utcnow=True),
                'image_id': image_id,
            })

        # Update the exposure count and metadata
        self.current_observation.exposure_list.append((image_id, fits_path))
        self.current_observation.current_exp += 1

    def get_standard_headers(self, observation=None):
        """ Get a set of standard headers

        Args:
            observation (`~pocs.scheduler.observation.Observation`, optional):
                The observation to use for header values. If None is given, use
                the `current_observation`

        Returns:
            dict: The stanard headers
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
        }

        return headers

    def analyze_recent(self, **kwargs):
        # Get the most recent exposure
        image_id, image_path = self.current_observation.last_exposure

        pass

    def update_tracking(self):
        pass

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
            self.logger.debug("Location: {}".format(self.location))

            # Create an EarthLocation for the mount
            self.earth_location = EarthLocation(
                lat=self.location.get('latitude'),
                lon=self.location.get('longitude'),
                height=self.location.get('elevation'),
            )
            self.observer = Observer(location=self.earth_location, name=name, timezone=timezone)
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

        a_simulator = 'camera' in self.config.get('simulator', [])
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

                if camera_config.get('primary', False):
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
                self.scheduler = module.Scheduler(self.observer, fields_file=fields_path, constraints=constraints)
                self.logger.debug("Scheduler created")
            except ImportError as e:
                raise error.NotFound(msg=e)
        else:
            self.logger.warning("Fields file does not exist: {}".format(fields_file))


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
