import glob
import os
import time

from datetime import datetime

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord
from astropy.io import fits

from . import PanBase

from .utils import current_time
from .utils import error
from .utils import images
from .utils import list_connected_cameras
from .utils import load_module


class Observatory(PanBase):

    def __init__(self, *args, **kwargs):
        """ Main Observatory class

        Starts up the observatory. Reads config file, sets up location,
        dates, mount, cameras, and weather station

        """
        super(Observatory, self).__init__(*args, **kwargs)

        self.logger.info('\tInitializing observatory')

        # Setup information about site location
        self.logger.info('\t\t Setting up location')
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

        self.mount.observer = self.scheduler

        # The current target
        self.observed_targets = []
        self.current_target = None

        self._image_dir = self.config['directories']['images']
        self.logger.info('\t Observatory initialized')

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_dark(self):
        horizon = self.location.get('twilight_horizon', -12 * u.degree)

        is_dark = self.scheduler.is_night(current_time(), horizon=horizon)

        self.logger.debug("Is dark (☉ < {}): {}".format(horizon, is_dark))
        return is_dark

    @property
    def sidereal_time(self):
        return self.scheduler.local_sidereal_time(current_time())

    @property
    def primary_camera(self):
        self.logger.debug("Getting primary camera: {}".format(self._primary_camera))
        return self.cameras.get(self._primary_camera, None)

##################################################################################################
# Methods
##################################################################################################

    def power_down(self):
        self.logger.debug("Shutting down observatory")

        # Stop cameras if exposing

    def status(self):
        """ """
        status = {}
        try:
            if self.mount.is_initialized:
                status['mount'] = self.mount.status()

                # Get the HA
                status['mount']['current_ha'] = self.scheduler.target_hour_angle(
                    current_time(), self.mount.get_current_coordinates())

                if self.mount.has_target:
                    status['mount']['target_ha'] = self.scheduler.target_hour_angle(
                        current_time(), self.mount.get_target_coordinates())

            t = current_time()
            local_time = str(datetime.now()).split('.')[0]

            status['scheduler'] = {
                'siderealtime': str(self.sidereal_time),
                'utctime': t,
                'localtime': local_time,
                'local_evening_astro_time': self.scheduler.twilight_evening_astronomical(t, which='next'),
                'local_morning_astro_time': self.scheduler.twilight_morning_astronomical(t, which='next'),
                'local_sun_set_time': self.scheduler.sun_set_time(t),
                'local_sun_rise_time': self.scheduler.sun_rise_time(t),
                'local_moon_alt': self.scheduler.moon_altaz(t).alt,
                'local_moon_illumination': self.scheduler.moon_illumination(t),
                'local_moon_phase': self.scheduler.moon_phase(t),
            }
            if self.current_target:
                status['target'] = self.current_target.status()

        except Exception as e:
            self.logger.warning("Can't get observatory status: {}".format(e))

        return status

    def construct_filename(self, guide=False):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera

        Returns:
            str:    Filename format
        """

        if guide:
            image_name = 'guide.cr2'
        else:
            image_name = "{:03.0f}_{:03.0f}.cr2".format(
                self.current_target.visit_num, self.current_target.current_visit.exp_num)

        filename = os.path.join(
            self.current_target.target_dir,
            image_name
        )

        return filename

    def observe(self):
        """ Make an observation for the current target.

        This method gets the current target's visit and takes the next
        exposure corresponding to the current observation.

        Returns:
            observation:    An `Observation` object.
        """

        # Get the current visit
        images = []
        try:
            self.logger.debug("Getting visit to observe")
            visit = self.current_target.get_visit()
            self.logger.debug("Visit: {}".format(visit))

            if not visit.done_exposing:
                try:
                    # We split filename so camera name is appended
                    self.logger.debug("Taking exposure for visit")
                    images = visit.take_exposures()
                except Exception as e:
                    self.logger.error("Problem with observing: {}".format(e))
            else:
                raise IndexError()
        except IndexError:
            self.logger.debug("No more exposures left for visit")
        finally:
            return images

    def get_target(self):
        """ Gets the next target from the scheduler

        Returns:
            target(Target or None):    An instance of the `pocs.Target` class or None.
        """

        # self.current_target = None

        try:
            self.logger.debug("Getting target for observatory using cameras: {}".format(self.cameras))
            target = self.scheduler.get_target()
        except Exception as e:
            raise error.PanError("Can't get target: {}".format(e))

        if target is not None:
            self.logger.debug("Got target for observatory: {}".format(target))

            if self.current_target == target:
                self.logger.debug("Resetting visits for {}".format(target))
                self.current_target.reset_visits()
            else:
                # If we already have a target, add it to the observed list
                # self.observed_targets.append(self.current_target)
                self.current_target = target
                self.logger.debug("Setting new current target")
        else:
            self.logger.warning("No targets found")

        self.logger.debug("Returning new target")
        return target

    def analyze_recent(self, **kwargs):
        """ Analyze the most recent `exposure`

        Converts the raw CR2 images into FITS and measures the offset. Does some
        bookkeeping. Information about the exposure, including the offset from the
        `reference_image` is returned.
        """
        target = self.current_target
        self.logger.debug("For analyzing: Target: {}".format(target))

        observation = target.current_visit
        self.logger.debug("For analyzing: Observation: {}".format(observation))

        exposure = observation.current_exposure
        self.logger.debug("For analyzing: Exposure: {}".format(exposure))

        # Get the standard FITS headers. Includes information about target
        fits_headers = self._get_standard_headers(target=target)
        fits_headers['title'] = target.name

        try:
            kwargs = {}
            if 'ra_center' in target.guide_wcsinfo:
                kwargs['ra'] = target.guide_wcsinfo['ra_center'].value
            if 'dec_center' in target.guide_wcsinfo:
                kwargs['dec'] = target.guide_wcsinfo['dec_center'].value
            if 'fieldw' in target.guide_wcsinfo:
                kwargs['radius'] = target.guide_wcsinfo['fieldw'].value
            else:
                kwargs['radius'] = 15.0

            # Process the raw images (just makes a pretty right now - we solved above and offset below)
            self.logger.debug("Starting image processing")
            exposure.process_images(fits_headers=fits_headers, solve=False, **kwargs)
        except Exception as e:
            self.logger.warning("Problem analyzing: {}".format(e))

        self.logger.debug("Getting offset from guide")
        offset_info = target.get_image_offset(exposure, with_plot=True)

        return offset_info

    def update_tracking(self):
        target = self.current_target
        pass

        # Make sure we have a target
        if target.current_visit is not None:

            offset_info = target.offset_info

            ra_delta_rate = offset_info.get('ra_delta_rate', 0.0)
            if ra_delta_rate != 0.0:
                self.logger.debug("Delta RA Rate: {}".format(ra_delta_rate))
                self.mount.set_tracking_rate(delta=ra_delta_rate)

            # Get the delay for the RA and Dec and adjust mount accordingly.
            for direction in ['dec', 'ra']:
                next

                # Now adjust for existing offset
                key = '{}_ms_offset'.format(direction)
                self.logger.debug("{}".format(key))

                if key in offset_info:
                    self.logger.debug("Check offset values for {} {}".format(direction, target.offset_info))

                    # Get the offset infomation
                    ms_offset = offset_info.get(key, 0)
                    if isinstance(ms_offset, u.Quantity):
                        ms_offset = ms_offset.value
                    ms_offset = int(ms_offset)

                    # Only adjust a reasonable offset
                    self.logger.debug("Checking {} {}".format(key, ms_offset))
                    if abs(ms_offset) > 10.0 and abs(ms_offset) <= 5000.0:

                        # Add some offset to the offset
                        # One-fourth of time. FIXME
                        processing_time_delay = int(ms_offset / 4)
                        self.logger.debug("Processing time delay: {}".format(processing_time_delay))

                        ms_offset = ms_offset + processing_time_delay
                        self.logger.debug("Total offset: {}".format(ms_offset))

                        if direction == 'ra':
                            if ms_offset > 0:
                                direction_cardinal = 'west'
                            else:
                                direction_cardinal = 'east'
                        elif direction == 'dec':
                            if ms_offset > 0:
                                direction_cardinal = 'south'
                            else:
                                direction_cardinal = 'north'

                        # Now that we have direction, all ms are positive
                        ms_offset = abs(ms_offset)

                        move_dir = 'move_ms_{}'.format(direction_cardinal)
                        move_ms = "{:05.0f}".format(ms_offset)
                        self.logger.debug("Adjusting tracking by {} to direction {}".format(move_ms, move_dir))

                        self.mount.serial_query(move_dir, move_ms)

                        # The above is a non-blocking command but if we issue the next command (via the for loop)
                        # then it will override the above, so we manually block for one second
                        time.sleep(abs(ms_offset) / 1000)
                    else:
                        self.logger.debug("Offset not in range")

        # Reset offset_info
        target.offset_info = {}

    def get_separation(self, guide_image, return_center=False):
        """ Adjusts pointing error from the most recent image.

        Receives a future from an asyncio call (e.g.,`wait_until_files_exist`) that contains
        filename of recent image. Uses utility function to return pointing error. If the error
        is off by some threshold, sync the coordinates to the center and reacquire the target.
        Iterate on process until threshold is met then start tracking.

        Parameters
        ----------
        future : {asyncio.Future}
            Future from returned from asyncio call, `.get_result` contains filename of image.

        Returns
        -------
        u.Quantity
            The separation between the center of the solved image and the target.
        """
        self.logger.debug("Getting pointing error")
        self.say("Ok, I've got the guide picture, let's see how close we are")

        separation = 0 * u.deg
        self.logger.debug("Default separation: {}".format(separation))

        self.logger.debug("Task completed successfully, getting image name")

        fname = guide_image

        self.logger.debug("Processing image: {}".format(fname))

        target = self.observatory.current_target

        fits_headers = self._get_standard_headers(target=target)
        self.logger.debug("Guide headers: {}".format(fits_headers))

        kwargs = {}
        if 'ra_center' in target.guide_wcsinfo:
            kwargs['ra'] = target.guide_wcsinfo['ra_center'].value
        if 'dec_center' in target.guide_wcsinfo:
            kwargs['dec'] = target.guide_wcsinfo['dec_center'].value
        if 'fieldw' in target.guide_wcsinfo:
            kwargs['radius'] = target.guide_wcsinfo['fieldw'].value

        self.logger.debug("Processing CR2 files with kwargs: {}".format(kwargs))
        processed_info = images.process_cr2(fname, fits_headers=fits_headers, timeout=45, **kwargs)
        # self.logger.debug("Processed info: {}".format(processed_info))

        # Use the solve file
        fits_fname = processed_info.get('solved_fits_file', None)

        if os.path.exists(fits_fname):
            # Get the WCS info and the HEADER info
            self.logger.debug("Getting WCS and FITS headers for: {}".format(fits_fname))

            wcs_info = images.get_wcsinfo(fits_fname)

            # Save guide wcsinfo to use for future solves
            target.guide_wcsinfo = wcs_info
            self.logger.debug("WCS Info: {}".format(target.guide_wcsinfo))

            target = None
            with fits.open(fits_fname) as hdulist:
                hdu = hdulist[0]
                # self.logger.debug("FITS Headers: {}".format(hdu.header))

                target = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)
                self.logger.debug("Target coords: {}".format(target))

            # Create two coordinates
            center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
            self.logger.debug("Center coords: {}".format(center))

            if target is not None:
                separation = center.separation(target)

            if return_center:
                return separation, center

        return separation


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
            horizon = config_site.get('horizon', 30) * u.degree
            twilight_horizon = config_site.get('twilight_horizon', -18) * u.degree

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

        mount_info['name'] = self.config.get('name')
        mount_info['utc_offset'] = self.location.get('utc_offset', '0.0')
        mount_info['mount_dir'] = self.config['directories']['mounts']
        mount_info['model'] = mount_info.get('model', '30')

        try:
            # Make the mount include site information
            mount = module.Mount(mount_info, location=self.earth_location)
        except ImportError:
            raise error.NotFound(msg=model)

        self.mount = mount
        self.logger.debug('Mount created')

    def _create_cameras(self, **kwargs):
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
        if kwargs.get('camera_info') is None:
            camera_info = self.config.get('cameras')

        self.logger.debug("Camera config: \n {}".format(camera_info))

        a_simulator = any(c in self.config.get('simulator') for c in ['camera', 'all'])
        if a_simulator:
            self.logger.debug("Using simulator for camera")

        ports = list()
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

            # Assign an auto-detected port. If none are left, skip
            if not a_simulator and auto_detect:
                try:
                    camera_config['port'] = ports.pop()
                except IndexError:
                    self.logger.warning("No ports left for {}, skipping.".format(cam_name))
                    continue

            camera_config['name'] = cam_name
            camera_config['image_dir'] = self.config['directories']['images']

            if not a_simulator:
                camera_model = camera_config.get('model')
            else:
                camera_model = 'simulator'

            self.logger.debug('Creating camera: {}'.format(camera_model))

            try:
                module = load_module('pocs.camera.{}'.format(camera_model))
                self.logger.debug('Camera module: {}'.format(module))
                cam = module.Camera(camera_config)

                self.logger.debug("Camera created: {} {}".format(cam.name, cam.uid))

                if cam.uid == camera_info.get('primary'):
                    cam.is_primary = True

                if cam.is_primary:
                    self._primary_camera = cam.name

                if cam.uid == camera_info.get('guide'):
                    cam.is_guide = True

                self.cameras[cam_name] = cam

            except ImportError:
                raise error.NotFound(msg=camera_model)

        if len(self.cameras) == 0:
            raise error.NotFound(msg="No cameras available. Exiting.", exit=True)

        self.logger.debug("Cameras created.")

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        scheduler_config = self.config.get('scheduler', {})
        scheduler_type = scheduler_config.get('type', 'core')

        # Read the targets from the file
        targets_file = scheduler_config.get('targets_file')
        targets_path = os.path.join(self.config['directories']['targets'], targets_file)

        if os.path.exists(targets_path):
            self.logger.debug('Creating scheduler: {}'.format(targets_path))

            try:
                # Load the required module
                module = load_module('pocs.scheduler.{}'.format(scheduler_type))

                # Create the Scheduler instance
                self.scheduler = module.Scheduler(
                    targets_file=targets_path,
                    location=self.earth_location,
                )
                self.logger.debug("Scheduler created")
            except ImportError as e:
                raise error.NotFound(msg=e)
        else:
            self.logger.warning("Targets file does not exist: {}".format(targets_path))

    def _get_standard_headers(self, target=None):
        if target is None:
            target = self.current_target

        self.logger.debug("For analyzing: Target: {}".format(target))

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
