import os
import time

from collections import OrderedDict
from datetime import datetime
import subprocess
from glob import glob

from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_moon
from astropy.coordinates import get_sun
from astropy.io import fits

from pocs.base import PanBase
import pocs.dome
from pocs.images import Image
from pocs.scheduler.constraint import Duration
from pocs.scheduler.constraint import MoonAvoidance
from pocs.scheduler.constraint import Altitude
from pocs.scheduler.observation import Observation
from pocs.scheduler.field import Field
from pocs.utils import current_time
from pocs.utils import flatten_time
from pocs.utils import altaz_to_radec
from pocs.utils import CountdownTimer
from pocs.utils import error
from pocs.utils import horizon as horizon_utils
from pocs.utils import load_module
from pocs.camera import AbstractCamera


class Observatory(PanBase):

    def __init__(self, cameras=None, *args, **kwargs):
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
        self.dome = pocs.dome.create_dome_from_config(self.config, logger=self.logger)

        self.logger.info('\tSetting up scheduler')
        self.scheduler = None
        self._create_scheduler()

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
        return self.scheduler.current_observation

    @current_observation.setter
    def current_observation(self, new_observation):
        self.scheduler.current_observation = new_observation

    @property
    def has_dome(self):
        return self.dome is not None


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

    def take_flat_fields(self,
                         which='evening',
                         alt=None,
                         az=None,
                         min_counts=1000,
                         max_counts=12000,
                         target_adu_percentage=0.5,
                         initial_exptime=3.,
                         max_exptime=120.,
                         camera_list=None,
                         bias=2048,
                         max_num_exposures=10,
                         ):  # pragma: no cover
        """Take flat fields.
        This method will slew the mount to the given AltAz coordinates(which
        should be roughly opposite of the setting sun) and then begin the flat-field
        procedure. The first image starts with a simple 1 second exposure and
        after each image is taken the average counts are analyzed and the exposure
        time is adjusted to try to keep the counts close to `target_adu_percentage`
        of the `(max_counts + min_counts) - bias`.
        The next exposure time is calculated as:
            ```
                exp_time = int(previous_exp_time * (target_adu / counts) *
                           (2.0 ** (elapsed_time / 180.0)) + 0.5)
            ```
            Under - and over-exposed images are rejected. If image is saturated with
            a short exposure the method will wait 60 seconds before beginning next
            exposure.
            Optionally, the method can also take dark exposures of equal exposure
            time to each flat-field image.
        Args:
            which (str, optional): Specify either 'evening' or 'morning' to lookup coordinates
                in config, default 'evening'.
            alt (float, optional): Altitude for flats, default None.
            az (float, optional): Azimuth for flats, default None.
            min_counts (int, optional): Minimum ADU count.
            max_counts (int, optional): Maximum ADU count.
            target_adu_percentage (float, optional): Exposure time will be adjust so
                that counts are close to: target * (`min_counts` + `max_counts`). Defaults
                to 0.5.
            initial_exptime (float, optional): Start the flat fields with this exposure
                time, default 3 seconds.
            max_exptime (float, optional): Maximum exposure time before stopping.
            camera_list (list, optional): List of cameras to use for flat-fielding.
            bias (int, optional): Default bias for the cameras.
            max_num_exposures (int, optional): Maximum number of flats to take.
        """
        if camera_list is None:
            camera_list = list(self.cameras.keys())

        target_adu = target_adu_percentage * (min_counts + max_counts)

        # Get the sun direction multiplier used to determine if exposure
        # times are increasing or decreasing.
        if which == 'evening':
            sun_direction = 1
        else:
            sun_direction = -1

        # Setup initial exposure times.
        exp_times = {cam_name: [initial_exptime * u.second] for cam_name in camera_list}

        # Create the observation.
        flat_obs = self._create_flat_field_observation(
            alt=alt, az=az, initial_exptime=initial_exptime
        )

        # A countdown timeout for the mount slewing.
        slew_timer = CountdownTimer(5 * u.minute)

        keep_taking_flats = True
        while keep_taking_flats:
            # Slew to the flat-field (with 5 minute timeout).
            self.logger.debug("Slewing to flat-field coords: {}".format(flat_obs.field))
            self.mount.set_target_coordinates(flat_obs.field)
            self.mount.slew_to_target()
            slew_timer.restart()
            while not self.mount.is_tracking and not slew_timer.expired():
                self.logger.debug("Slewing to target")
                time.sleep(5)
                self.status()

            # Make sure we safely arrive and not timed out.
            if slew_timer.expired() and not self.mount.is_tracking:
                raise error.Timeout(f'Problem slewing to flat field.')  # pragma: no cover

            start_time = current_time()
            fits_headers = self.get_standard_headers(observation=flat_obs)
            fits_headers['start_time'] = flatten_time(start_time)

            # Take the observations.
            camera_events = dict()
            for cam_name in camera_list:
                camera = self.cameras[cam_name]
                exp_time = exp_times[cam_name][-1].value
                filename = os.path.normpath(os.path.join(
                    flat_obs.directory,
                    camera.uid,
                    flat_obs.seq_time,
                    f'flat_{flat_obs.current_exp_num:02d}.{camera.file_extension}'
                ))
                # Take picture and get event.
                camera_event = camera.take_observation(
                    flat_obs,
                    fits_headers,
                    filename=filename,
                    exp_time=exp_time
                )
                camera_events[cam_name] = {
                    'event': camera_event,
                    'filename': filename,
                }

            # Block until done exposing on all cameras
            while not all([info['event'].is_set() for info in camera_events.values()]):
                self.logger.debug('Waiting for flat-field image')
                time.sleep(1)

            # Check the counts for each image.
            is_saturated = False
            for cam_name, info in camera_events.items():

                # Make sure we can find the file.
                img_file = info['filename'].replace('.cr2', '.fits')
                if not os.path.exists(img_file):
                    img_file = img_file.replace('.fits', '.fits.fz')
                    if not os.path.exists(img_file):  # pragma: no cover
                        self.logger.warning(f"No flat file {img_file} found, skipping")
                        continue

                self.logger.debug("Checking counts for {}".format(img_file))

                # Get the bias subtracted data.
                data = fits.getdata(img_file) - bias

                # Simple mean works just as well as sigma_clipping and is quicker for RGB.
                counts = data.mean()
                self.logger.debug("Counts: {:.02f}".format(counts))

                # Check we are above minimum counts.
                if counts < min_counts:
                    self.logger.debug("Counts are too low, flat should be discarded")
                    # TODO(wtgee) Mark in headers? Skip rest of loop?

                # Check we are below maximum counts.
                if counts >= max_counts:
                    self.logger.debug("Image is saturated")
                    is_saturated = True
                    # TODO(wtgee) Mark in headers? Skip rest of loop?

                # Get suggested exposure time.
                elapsed_time = (current_time() - start_time).sec
                self.logger.debug("Elapsed time: {:.02f}".format(elapsed_time))
                previous_exp_time = exp_times[cam_name][-1].value

                # TODO(wtgee) Document this better.
                exptime = int(previous_exp_time * (target_adu / counts) *
                              (2.0 ** (sun_direction * (elapsed_time / 180.0))) + 0.5)

                self.logger.debug(f"Suggested exp_time for {cam_name}: {exptime:.02f}")
                exp_times[cam_name].append(exptime * u.second)

            # Stop flats if we are going on too long.
            self.logger.debug("Checking for too many exposures")
            if any([len(t) - 1 >= max_num_exposures for t in exp_times.values()]):
                self.logger.debug(f"Have max exposures ({max_num_exposures}), stopping.")
                keep_taking_flats = False

            # Stop flats if any time is greater than max.
            self.logger.debug("Checking for long exposures")
            if any([t[-1].value >= max_exptime for t in exp_times.values()]):
                self.logger.debug("Exposure times greater than max, stopping flat fields")
                keep_taking_flats = False

            self.logger.debug("Checking for saturation on short exposure")
            if is_saturated and exp_times[cam_name][-1].value <= 2:
                self.logger.debug("Saturated short exposure, waiting 60 seconds")
                max_num_exposures += 1
                time.sleep(60)
                keep_taking_flats = False

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
            utc_offset = config_site.get('utc_offset')

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
                'utc_offset': utc_offset,
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

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        scheduler_config = self.config.get('scheduler', {})
        scheduler_type = scheduler_config.get('type', 'dispatch')

        # Read the targets from the file
        fields_file = scheduler_config.get('fields_file', 'simple.yaml')
        fields_path = os.path.join(self.config['directories'][
                                   'targets'], fields_file)
        self.logger.debug('Creating scheduler: {}'.format(fields_path))

        if os.path.exists(fields_path):

            try:
                # Load the required module
                module = load_module(
                    'pocs.scheduler.{}'.format(scheduler_type))

                obstruction_list = self.config['location'].get('obstructions', list())
                default_horizon = self.config['location'].get('horizon', 30 * u.degree)

                horizon_line = horizon_utils.Horizon(
                    obstructions=obstruction_list,
                    default_horizon=default_horizon.value
                )

                # Simple constraint for now
                constraints = [
                    Altitude(horizon=horizon_line),
                    MoonAvoidance(),
                    Duration(default_horizon)
                ]

                # Create the Scheduler instance
                self.scheduler = module.Scheduler(
                    self.observer, fields_file=fields_path, constraints=constraints)
                self.logger.debug("Scheduler created")
            except ImportError as e:
                raise error.NotFound(msg=e)
        else:
            raise error.NotFound(
                msg="Fields file does not exist: {}".format(fields_file))

    def _create_flat_field_observation(self,
                                       alt=70,  # degrees
                                       az=None,
                                       field_name='Evening Flat',
                                       flat_time=None,
                                       initial_exptime=5):
        """Small convenince wrapper to create a flat-field Observation.

        Flat-fields are specified by AltAz coordinates so this method is just a helper
        to look up the current RA-Dec coordaintes based on the unit's location and
        the current time (or `flat_time` if provided).

        If no azimuth is provided this will figure out the azimuth of the sun at
        `flat_time` and use that position minus 180 degrees.

        Args:
            alt (float, optional): Altitude desired, default 70 degrees.
            az (float, optional): Azimuth desired in degrees, defaults to a position
                -180 degrees opposite the sun at `flat_time`.
            field_name (str, optional): Name of the field, which will also be directory
                name. Note that it is probably best to pass the camera.uid as name.
            flat_time (`astropy.time.Time`, optional): The time at which the flats
                will be taken, default `now`.
            initial_exptime (int, optional): Initial exptime in seconds, default 5.
        Returns:
            `pocs.scheduler.Observation`: Information about the flat-field.
        """
        self.logger.debug("Creating flat-field observation")

        if flat_time is None:
            flat_time = current_time()

        # Get an azimuth that is roughly opposite the sun.
        if az is None:
            sun_pos = self.observer.altaz(flat_time, target=get_sun(flat_time))
            az = sun_pos.az.value - 180.  # Opposite the sun

        # Construct RA/Dec coords from the Alt Az.
        flat_coords = altaz_to_radec(
            alt=alt,
            az=az,
            location=self.earth_location,
            obstime=flat_time)

        field = Field(field_name, flat_coords)
        flat_obs = Observation(field, exp_time=initial_exptime * u.second)

        # Note different 'flat' concepts.
        flat_obs.seq_time = flatten_time(flat_time)

        # Setup the directory to store images.
        flat_obs._directory = os.path.join(
            self.config['directories']['images'],
            'flats',
        )
        self.logger.debug("Flat-field observation: {}".format(flat_obs))
        return flat_obs
