import os.path

from astropy import units as u
from astropy.time import Time

from collections import OrderedDict

from ..utils.logger import get_logger
from ..utils.config import load_config
from ..utils import error
from ..utils.images import cr2_to_fits


class Observation(object):

    class Exposure(object):

        """ An individual exposure taken by an `Observation` """

        def __init__(self, exptime=120, filter_type=None):

            self.exptime = exptime
            self.filter_type = filter_type

    def __init__(self, obs_config=dict(), cameras=None):
        """An object which describes a single observation.

        Each observation can have a number of different `Exposure`s based on the config settings.
        For each type of exposure ('primary' or 'secondary') there are `[type]_nexp` `Exposure`
            objects created. Each of these `Exposure`s has a list of cameras. (See `Exposure` for details)

        Example::

              - analyze: false
                primary_exptime: 300
                primary_filter: null
                primary_nexp: 3
                secondary_exptime: 300
                secondary_filter: null
                secondary_nexp: 3

        Args:
            obs_config (dictionary): a dictionary describing the observation as read from
                the YAML file, see Example.
            cameras(list[panoptes.camera]): A list of `panoptes.camera` objects to use for
                this observation.

        """
        self.config = load_config()
        self.logger = get_logger(self)

        self.cameras = cameras

        self.logger.debug("Camears for observation: {}".format(cameras))
        self.exposures = self._create_exposures(obs_config)

        self.images = OrderedDict()
        self._images_exist = False

        self.reset_exposures()

##################################################################################################
# Properties
##################################################################################################

    @property
    def has_images(self):
        return len(self.images) > 0

    @property
    def is_exposing(self):
        return self._is_exposing

    @property
    def images_exist(self):
        """ Whether or not the images indicated by `self.images` exists.

        The `images` attribute is set when the exposure starts, so this is
        effectively a test for if the exposure has ended correctly.
        """
        self._complete = all(os.path.exists(f) for f in list(self.images.keys()))

        if self._complete:
            self._is_exposing = False

        return self._complete

    @property
    def current_exposure(self):
        try:
            self.logger.debug("Current exp num: {}".format(self._current_exposure))
            exp = self.exposures[self._current_exposure]

            self.logger.debug("Current exposure: {}".format(exp))
        except IndexError:
            self.logger.debug("No exposures left.")
            exp = None

        return exp

    @property
    def done_exposing(self):
        """ Bool indicating whether or not any exposures are left """
        self.logger.debug("Checking if observation has exposures")

        return self._done_exposing

    @property
    def complete(self):
        return self.done_exposing


##################################################################################################
# Methods
##################################################################################################

    def get_exposure_iter(self):
        """ Yields the next exposure """

        for num, exposure in enumerate(self.exposures):
            self.logger.debug("Getting next exposure ({})".format(exposure))
            self._current_exposure = self._current_exposure + 1

            if num == len(self.exposures) - 1:
                self._done_exposing = True

            yield exposure

    def reset_exposures(self):
        """ Resets the exposures iterator """
        self.exposure_iterator = self.get_exposure_iter()
        self._done_exposing = False
        self._base = len(self.images)
        self._current_exposure = self._base
        self._is_exposing = False
        self._complete = False

    def take_exposure(self):
        """ Take the next exposure """
        try:
            exposure = next(self.exposure_iterator)
            # One start_time for this round of exposures
            start_time = Time.now().isot

            obs_info = {}

            # Take a picture with each camera
            self.logger.debug("Cameras to expose: {}".format(self.cameras))
            for cam_name, cam in self.cameras.items():
                # Start exposure
                img_file = cam.take_exposure(seconds=exposure.exptime)
                self._is_exposing = True

                obs_info = {
                    'camera_id': cam.uid,
                    'camera_name': cam_name,
                    'img_file': img_file,
                    'filter': exposure.filter_type,
                    'start_time': start_time,
                }
                self.logger.debug("{}".format(obs_info))
                self.images[img_file] = obs_info

        except error.InvalidCommand as e:
            self.logger.warning("{} is already running a command.".format(cam.name))
            self._is_exposing = False
        except Exception as e:
            self.logger.warning("Can't take exposure from Observation: {}".format(e))
            self._is_exposing = False

    def estimate_duration(self, overhead=0 * u.s):
        """Method to estimate the duration of a single observation.

        A quick and dirty estimation of the time it takes to execute the
        observation.  Does not take overheads such as slewing, image readout,
        or image download in to consideration.

        Args:
            overhead (astropy.units.Quantity): The overhead time for the observation in
            units which are reducible to seconds.  This is the overhead which occurs
            for each exposure.

        Returns:
            astropy.units.Quantity: The duration (with units of seconds).
        """
        duration = max([(self.primary_exptime + overhead) * self.primary_nexp,
                        (self.secondary_exptime + overhead) * self.secondary_nexp])
        self.logger.debug('Observation duration estimated as {}'.format(duration))
        return duration

    def process_images(self, fits_headers={}):
        if self.images_exist:
            self.logger.debug("Processing images: {}".format(self.images))
            for img_name, img_info in self.images.items():
                if img_info.get('fits', None) is None:

                    self.logger.debug("Observation image to convert from cr2 to fits: {}".format(img_name))

                    fits_headers['detname'] = img_info.get('camera_id', '')

                    start_time = Time.now()
                    fits_fname = cr2_to_fits(img_name, fits_headers=fits_headers)
                    end_time = Time.now()

                    self.logger.debug("Processing time: {}".format((start_time - end_time).to(u.s)))

                    self.images[img_name]['fits'] = fits_fname

##################################################################################################
# Private Methods
##################################################################################################

    def _create_exposures(self, obs_config):
        self.logger.debug("Creating exposures")

        primary_exptime = obs_config.get('primary_exptime', 120) * u.s
        primary_filter = obs_config.get('primary_filter', None)
        primary_nexp = obs_config.get('primary_nexp', 3)
        # analyze = obs_config.get('primary_analyze', False)

        primary_exposures = [self.Exposure(
            exptime=primary_exptime,
            filter_type=primary_filter,
        ) for n in range(primary_nexp)]
        self.logger.debug("Primary exposures: {}".format(primary_exposures))
        self.num_exposures = primary_nexp

        # secondary_exptime (assumes units of seconds, defaults to 120 seconds)
        # secondary_exptime = obs_config.get('secondary_exptime', 120) * u.s
        # secondary_nexp = obs_config.get('secondary_nexp', 0)
        # secondary_filter = obs_config.get('secondary_filter', None)

        # secondary_exposures = [Exposure(
        #     exptime=secondary_exptime,
        #     filter_type=secondary_filter,
        #     analyze=False,
        #     cameras=[c for c in cameras.values() if not c.is_primary],
        # ) for n in range(secondary_nexp)]

        # if secondary_nexp > primary_nexp:
        #     self.num_exposures = secondary_nexp

        # self.logger.debug("Secondary exposures: {}".format(secondary_exposures))

        return primary_exposures
