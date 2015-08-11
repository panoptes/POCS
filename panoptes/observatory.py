import os
import datetime
import importlib

import astropy.units as u
import astropy.coordinates as coords
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz

from . import mount as mount
from . import camera as camera
from . import scheduler as scheduler

from .utils.config import load_config
from .utils.logger import has_logger
from .utils import error as error

from astroplan import Observer

@has_logger
class Observatory(Observer):

    """
    Main Observatory class
    """

    def __init__(self, config=None, *args, **kwargs):
        """
        Starts up the observatory. Reads config file (TODO), sets up location,
        dates, mount, cameras, and weather station
        """
        assert config is not None, self.logger.warning( "Config not set for observatory")
        self.config = config

        self.logger.info('Initializing observatory')
        config_site = config['site']

       # Setup information about site location
        self.logger.info('\t Setting up observatory details')
        self._setup_observatory()

        self.mount = None
        self.scheduler = None
        self.cameras = list()

        # Create default mount and cameras. Should be read in by config file
        self.logger.info('\t Setting up mount')
        self._create_mount()

        self.logger.info('\t Setting up cameras')
        # self._create_cameras()

        self.logger.info('\t Setting up scheduler')
        self._create_scheduler()

    def get_target(self):
        """ Gets the next target from the scheduler """

        target = self.scheduler.get_target(self)

        return target

    def _setup_observatory(self, start_date=Time.now()):
        """
        Sets up the site and location details, for the observatory.

        These items are read from the 'site' config directive and include:
        * lat (latitude)
        * lon (longitude)
        * elevation
        * horizon

        """
        self.logger.info('Setting up site details of observatory')

        if 'site' in self.config:
            config_site = self.config.get('site')

            name = config_site.get('name')

            latitude = config_site.get('latitude') * u.degree
            longitude = config_site.get('longitude') * u.degree

            timezone = config_site.get('timezone')

            elevation = config_site.get('elevation', 0) * u.meter
            horizon = config_site.get('horizon', 0) * u.degree
            pressure = config_site.get('pressure', 0.680) * u.bar

            super().__init__(
                name=name,
                latitude=latitude,
                longitude=longitude,
                elevation=elevation,
                timezone=timezone,
                pressure=pressure,
            )

            self.horizon = horizon

            # Create an astropy EarthLocation
            # self.location = coords.EarthLocation(
            #     lat=latitude,
            #     lon=longitude,
            #     height=self.elevation,
            # )
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

        model = mount_info.get('model')

        self.logger.info('Creating mount: {}'.format(model))

        mount = None

        # Actually import the model of mount
        try:
            module = importlib.import_module(
                '.{}'.format(model), package='panoptes.mount')
        except ImportError as err:
            self.logger.warning(
                'ImportError. Check that the mount module exists and that all dependencies are installed (e.g. serial)')
            print(err)
            raise error.NotFound(model)

        # Make the mount include site information
        mount = module.Mount(config=mount_info, site=self.location)

        return mount

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
        camera_info = self.config.get('cameras')

        for camera in camera_info:
            # Actually import the model of camera
            camera_model = camera.get('model')
            try:
                module = importlib.import_module(
                    '.{}'.format(camera_model), 'panoptes.camera')
                cameras.append(module.Camera(config=camera))

            except ImportError as err:
                raise error.NotFound(msg=camera_model)

        self.cameras = cameras

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        # Read the targets from the file
        targets_path = os.path.join(
            self.config.get('base_dir'),
            self.config.get('targets', 'default_targets.yaml')
        )

        self.logger.info('\t Scheduler file: {}'.format(targets_path))
        self.scheduler = scheduler.Scheduler(target_list_file=targets_path)
