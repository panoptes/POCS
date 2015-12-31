import os
import time

import astropy.units as u
from astropy.coordinates import EarthLocation

from .utils.modules import load_module
from .utils import error
from .utils.logger import get_logger


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
        self.cameras = list()
        self._create_cameras()

        self.logger.info('\t\t Setting up scheduler')
        self.scheduler = None
        self._create_scheduler()

        self.logger.info('\t Observatory initialized')

##################################################################################################
# Methods
##################################################################################################

    def get_target(self):
        """ Gets the next target from the scheduler """

        self.logger.debug("Getting target for observatory")
        target = self.scheduler.get_target()
        self.logger.debug("Got target for observatory: {}".format(target))

        return target

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

        self.logger.debug('Creating mount: {}'.format(model))

        module = load_module('panoptes.mount.{}'.format(model))

        mount_info['name'] = self.config.get('name')
        mount_info['utc_offset'] = self.location.get('utc_offset', '0.0')
        mount_info['resources_dir'] = self.config.get('resources_dir')

        try:
            # Make the mount include site information
            mount = module.Mount(mount_info, location=self.earth_location)
        except ImportError:
            raise error.NotFound(msg=model)

        self.mount = mount
        self.logger.debug('Mount created')

    def _create_cameras(self, camera_info=None):
        """Creates a camera object(s)

        Creates a camera for each camera item listed in the config. Ensures the
        appropriate camera module is loaded.

        Note:
            This does not actually make a usb connection to the camera. To do so,
            call the 'camear.connect()' explicitly.

        Args:
            camera_info (dict): Configuration items for the cameras.

        Returns:
            list: A list of created camera objects.
        """
        if camera_info is None:
            camera_info = self.config.get('cameras')

        self.logger.debug("Camera config: \n {}".format(camera_info))

        cameras = list()

        for cam_num, camera_config in enumerate(camera_info):
            cam_name = 'Cam{}'.format(cam_num)
            camera_config['name'] = cam_name

            if 'camera' in self.config.get('simulator', False):
                camera_model = 'simulator'
            else:
                camera_model = camera_config.get('model')

            self.logger.debug('Creating camera: {}'.format(camera_model))

            try:
                module = load_module('panoptes.camera.{}'.format(camera_model))
                cam = module.Camera(camera_config)
                cameras.append(cam)
            except ImportError:
                raise error.NotFound(msg=camera_model)

        self.cameras = cameras
        self.logger.debug("Cameras created.")

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        scheduler_config = self.config.get('scheduler')

        # Read the targets from the file
        targets_path = os.path.join(
            self.config.get('base_dir'),
            'resources/conf_files/targets/',
            scheduler_config.get('targets_file')
        )

        scheduler_type = scheduler_config.get('type', 'simple')

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
