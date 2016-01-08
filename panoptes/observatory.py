import os
import time
import glob

from astropy.coordinates import EarthLocation
from astropy import units as u

from collections import OrderedDict

from .utils.modules import load_module
from .utils.logger import get_logger
from .utils import error, list_connected_cameras


class Observatory(object):

    """
    Main Observatory class
    """

    def __init__(self, config=None, *args, **kwargs):
        """
        Starts up the observatory. Reads config file, sets up location,
        dates, mount, cameras, and weather station
        """
        assert config is not None, self.logger.warning("Config not set for observatory")
        self.config = config

        self.logger = get_logger(self)
        self.logger.info('\tInitializing observatory')

        # Setup information about site location
        self.logger.info('\t\t Setting up location')
        self._setup_location()

        self.logger.info('\t\t Setting up mount')
        self.mount = None
        self._create_mount()

        self.logger.info('\t\t Setting up cameras')
        self.cameras = dict()
        self._create_cameras(auto_detect=kwargs.get('auto_detect', False))

        self.logger.info('\t\t Setting up scheduler')
        self.scheduler = None
        self._create_scheduler()

        # The current target
        self.observed_targets = OrderedDict()
        self.current_target = None

        self.logger.info('\t Observatory initialized')

##################################################################################################
# Properties
##################################################################################################

    @property
    def primary_camera(self):
        self.logger.debug("Getting primary camera: {}".format(self._primary_camera))
        return self.cameras.get(self._primary_camera, None)

##################################################################################################
# Methods
##################################################################################################

    def observe(self):
        """ Make an observation for the current target.

        This method gets the current target's visit and takes the next
        exposure corresponding to the current observation.

        Returns:
            observation:    An `Observation` object.
        """

        # Get the current visit
        observation = self.current_target.current_observation

        if observation.has_exposures:
            try:
                observation.take_exposure(self.cameras)
            except Exception as e:
                self.logger.error("Problem with taking exposures: {}".format(e))
        else:
            self.logger.debug("No more exposures left for observation")

        return observation

    def get_target(self):
        """ Gets the next target from the scheduler

        Returns:
            target(Target or None):    An instance of the `panoptes.Target` class or None.
        """

        self.logger.debug("Getting target for observatory using cameras: {}".format(self.cameras))
        target = self.scheduler.get_target(camera=self.primary_camera)
        self.logger.debug("Got target for observatory: {}".format(target))

        if target and not target.done_visiting:
            # If we already have a target, add it to the observed list
            if self.current_target is not None:
                self.observed_targets.append(self.current_target)
        else:
            target = None

        self.current_target = target

        return target


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

            latitude = config_site.get('latitude') * u.degree
            longitude = config_site.get('longitude') * u.degree

            timezone = config_site.get('timezone')
            utc_offset = config_site.get('utc_offset')

            pressure = config_site.get('pressure', 0.680) * u.bar
            elevation = config_site.get('elevation', 0) * u.meter
            horizon = config_site.get('horizon', 0) * u.degree

            self.location = {
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'elevation': elevation,
                'timezone': timezone,
                'utc_offset': utc_offset,
                'pressure': pressure,
                'horizon': horizon
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
            panoptes.mount:     Returns a sub-class of the mount type
        """
        if mount_info is None:
            mount_info = self.config.get('mount')

        if 'mount' in self.config.get('simulator', False):
            model = 'simulator'
        else:
            model = mount_info.get('model')
            port = mount_info.get('port')
            if len(glob.glob(port)) == 0:
                raise error.PanError(
                    msg="The mount port ({}) is not available. Use --simulator=mount for simulator. Exiting.".format(
                        port),
                    exit=True)

        self.logger.debug('Creating mount: {}'.format(model))

        module = load_module('panoptes.mount.{}'.format(model))

        mount_info['name'] = self.config.get('name')
        mount_info['utc_offset'] = self.location.get('utc_offset', '0.0')
        mount_info['mount_dir'] = self.config['directories']['mounts']

        try:
            # Make the mount include site information
            mount = module.Mount(mount_info, location=self.earth_location)
        except ImportError:
            raise error.NotFound(msg=model)

        self.mount = mount
        self.logger.debug('Mount created')

    def _create_cameras(self, camera_info=None, auto_detect=False):
        """Creates a camera object(s)

        Creates a camera for each camera item listed in the config. Ensures the
        appropriate camera module is loaded.

        Note:
            This does not actually make a usb connection to the camera. To do so,
            call the 'camear.connect()' explicitly.

        Args:
            camera_info (dict): Configuration items for the cameras.
            auto_detect(bool): Attempt to discover the camera ports rather than use config, defaults to False.

        Returns:
            list: A list of created camera objects.
        """
        if camera_info is None:
            camera_info = self.config.get('cameras')

        self.logger.debug("Camera config: \n {}".format(camera_info))

        not_a_simulator = 'camera' not in self.config.get('simulator')

        ports = list()

        if not_a_simulator and auto_detect:
            self.logger.debug("Auto-detecting ports for cameras")
            ports = list_connected_cameras()

            if len(ports) == 0:
                raise error.PanError(msg="No cameras detected. Use --simulator=camera for simulator.", exit=True)
            else:
                self.logger.debug("Detected Ports: {}".format(ports))

        for cam_num, camera_config in enumerate(camera_info):
            cam_name = 'Cam{:02d}'.format(cam_num)

            # Assign an auto-detected port. If none are left, skip
            if auto_detect:
                try:
                    camera_config['port'] = ports.pop()
                except IndexError:
                    self.logger.warning("No ports left for {}, skipping.".format(cam_name))
                    break

            camera_config['name'] = cam_name
            camera_config['image_dir'] = self.config['directories']['images']

            if not_a_simulator:
                camera_model = camera_config.get('model')
            else:
                camera_model = 'simulator'

            self.logger.debug('Creating camera: {}'.format(camera_model))

            try:
                module = load_module('panoptes.camera.{}'.format(camera_model))
                cam = module.Camera(camera_config)
                self.cameras[cam_name] = cam

                # If this is the primary (or only) camera, mark
                if camera_config.get('primary', False) or len(camera_info) == 0:
                    self._primary_camera = cam_name
            except ImportError:
                raise error.NotFound(msg=camera_model)

        self.logger.debug("Cameras created.")

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        scheduler_config = self.config.get('scheduler', {})

        targets_file = scheduler_config.get('targets_file')

        # Read the targets from the file
        targets_path = os.path.join(self.config['directories']['targets'], targets_file)

        scheduler_type = scheduler_config.get('type', 'core')

        try:
            module = load_module('panoptes.scheduler.{}'.format(scheduler_type))

            if os.path.exists(targets_path):
                self.logger.debug('Creating scheduler: {}'.format(targets_path))
                self.scheduler = module.Scheduler(targets_file=targets_path, location=self.earth_location)
                self.logger.debug("Scheduler created")
            else:
                self.logger.warning("Targets file does not exist: {}".format(targets_path))
        except ImportError as e:
            raise error.NotFound(msg=e)

##################################################################################################
# Private Utility Methods
##################################################################################################

    def track_target(self, target, hours=2.0):
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
