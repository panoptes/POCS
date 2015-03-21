import os

import ephem
import datetime

import importlib

import astropy.units as u
import astropy.coordinates as coords

import panoptes.mount as mount
import panoptes.camera as camera
import panoptes.scheduler as scheduler

import panoptes.utils.logger as logger
import panoptes.utils.config as config
import panoptes.utils.error as error


# @logger.set_log_level(level='debug')
@logger.has_logger
@config.has_config
class Observatory(object):

    """
    Main Observatory class
    """

    def __init__(self, targets_filename='default_targets.yaml'):
        """
        Starts up the observatory. Reads config file (TODO), sets up location,
        dates, mount, cameras, and weather station
        """

        self.logger.info('Initializing observatory')

       # Setup information about site location
        self.logger.info('\t Setting up observatory site')
        self.site = self.setup_site()

        # Read the targets from the file
        targets_path = os.path.join(self.config['base_dir'], targets_filename)

        self.logger.info('\t Setting up scheduler: {}'.format(targets_path))
        self.scheduler = scheduler.Scheduler(target_list_file=targets_path)

        # Create default mount and cameras. Should be read in by config file
        self.logger.info('\t Setting up mount')
        self.mount = self.create_mount()

        # self.cameras = self.create_cameras()

    def setup_site(self, start_date=ephem.now(), use_astropy=False):
        """
        Sets up the site, i.e. location details, for the observatory. These items
        are read from the 'site' config directive and include:
        * lat (latitude)
        * lon (longitude)
        * elevation
        * horizon

        Also sets up observatory.sun and observatory.moon computed from this site
        location.
        """
        self.logger.info('Seting up site details of observatory')
        site = ephem.Observer()
        earth_location = None

        if 'site' in self.config:
            config_site = self.config.get('site')

            lat = config_site.get('lat')
            lon = config_site.get('lon')
            lat_deg = config_site.get('lat_deg')
            lon_deg = config_site.get('lon_deg')

            elevation = float(config_site.get('elevation', 0))
            horizon = float(config_site.get('horizon', 0))

            # Create a ephem site location
            site.lat = lat
            site.lon = lon
            site.elevation = elevation
            site.horizon = horizon

            # Create an astropy EarthLocation
            earth_location = coords.EarthLocation(
                lat=lat_deg*u.deg,
                lon=lon_deg*u.deg,
                height=elevation*u.meter,
            )
        else:
            raise error.Error(msg='Bad site information')

        # Pressure initially set to 680.  This could be updated later.
        site.pressure = float(config_site.get('pressure', 680))

        # Static Initializations
        site.date = start_date

        # Update the sun and moon
        self.sun, self.moon = ephem.Sun(), ephem.Moon()
        self.sun.compute(site)
        self.moon.compute(site)

        if use_astropy:
            return earth_location
        else:
            return site

    def create_mount(self, mount_info=None):
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
            module = importlib.import_module('.{}'.format(model), 'panoptes.mount')
        except ImportError as err:
            raise error.NotFound(model)

        # Make the mount include site information
        mount = module.Mount(config=mount_info, site=self.site)

        return mount

    def create_cameras(self, camera_info=None):
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

        cameras = []

        for camera in camera_info:
            # Actually import the model of camera
            try:
                module = importlib.import_module('.{}'.format(camera.get('model')), 'panoptes.camera')
                cameras.append(module.Camera(config=camera))

            except ImportError as err:
                raise error.NotFound(msg=model)

        return cameras

    def get_target(self):

        target = self.scheduler.get_target(self)

        return target

    def heartbeat(self):
        """
        Touch a file each time signaling life
        """
        self.logger.debug('Touching heartbeat file')
        with open(self.heartbeat_filename, 'w') as fileobject:
            fileobject.write(str(datetime.datetime.now()) + "\n")

    def horizon(self, alt, az):
        '''Function to evaluate whether a particular alt, az is
        above the horizon

        NOTE: This could be done better with pyephem
        '''
        assert isinstance(alt, u.Quantity)
        assert isinstance(az, u.Quantity)

        horizon = float(self.config.get('site.horizon', 0)) * u.deg

        if alt > horizon:
            return True
        else:
            return False

    def is_dark(self):
        """
        Need to calculate day/night for site.

        NOTE: This could be done better with pyephem
        """
        self.logger.debug('Calculating is_dark.')

        self.site.date = ephem.now()
        self.sun.compute(self.site)

        dark_horizon = float(self.config.get('twilight_horizon', -12))

        self.is_dark = self.sun.alt < dark_horizon

        return self.is_dark
