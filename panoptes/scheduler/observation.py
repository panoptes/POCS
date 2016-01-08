import os.path

from astropy import units as u
from astropy.time import Time

from collections import OrderedDict

from ..utils.logger import get_logger
from ..utils.config import load_config
from ..utils import error


class Exposure(object):

    """ An individual exposure taken by an `Observation` """

    def __init__(self, exptime=120, filter=None, analyze=False, camera_id=None):

        self.exptime = exptime
        self.filter = filter
        self.camera_id = camera_id

        self.filename = None

        self._file_exists = False

    @property
    def file_exists(self):
        """ Wether or not the file indicated by `self.filename` exists.

        The `filename` attribute is set when the exposure starts, so this is
        effectively a test for if the exposure has ended correctly.
        """
        self._file_exists = os.path.exists(self.filename)

        return self._file_exists


class Observation(object):

    def __init__(self, obs_config=dict()):
        """An object which describes a single observation.

        Args:
            obs_config (dictionary): a dictionary describing the observation as read from
            the YAML file.

        Example:
              - analyze: false
                primary_exptime: 300
                primary_filter: null
                primary_nexp: 3
                secondary_exptime: 300
                secondary_filter: null
                secondary_nexp: 3


        """
        self.config = load_config()
        self.logger = get_logger(self)

        self.exposures = self._create_exposures(obs_config)

        self._is_exposing = False

##################################################################################################
# Properties
##################################################################################################

    @property
    def is_exposing(self):
        return self._is_exposing

    @property
    def has_exposures(self):
        """ Bool indicating whether or not any exposures are left """
        return self.has_primary_exposures and self.has_secondary_exposures

    @property
    def has_primary_exposures(self):
        """ Bool indicating whether or not any primary exposures are left """
        return len(self.primary_images) < self.primary_nexp

    @property
    def has_secondary_exposures(self):
        """ Bool indicating whether or not any secondary exposures are left """
        return len(self.secondary_images) < self.secondary_nexp

##################################################################################################
# Methods
##################################################################################################

    def take_exposure(self, cameras):
        """ Takes an exposure with each camera in `cameras`.

        If this observation still has exposures left, loop through each camera given in `cameras`
        and `take_exposure` depending on `primary` or `secondary` type. Append `img_file` to appropriate
        list.

        Note:
            An `Observation` can have any combination of exposures for the primary or secondary cameras.
        """
        assert isinstance(cameras, list), self.logger.warning("take_exposure expects a list of cameras")

        try:

            primary_imgs = ()
            secondary_imgs = ()

            # One start_time for this round of exposures
            start_time = Time.now().isot

            # Take a picture with each camera
            for cam in self.cameras:
                # If marked primary or if there is only one camera
                is_primary = cam.is_primary or len(self.cameras) == 1

                # Get the number of seconds to exposure for
                seconds = 0
                if is_primary and self.has_primary_exposures:
                    seconds = self.primary_exptime.value
                elif self.has_secondary_exposures:
                    seconds = self.secondary_exptime.value

                # If we didn't get an exposure time for this camera, continue to next camera
                if seconds == 0:
                    continue

                # Start exposure
                img_file = cam.take_exposure(seconds=seconds)
                self._is_exposing = True

                obs_info = {
                    'camera_id': cam.uid,
                    'img_file': img_file,
                    'analyze': is_primary and self.analyze,
                }
                self.logger.debug("{}".format(obs_info))

                # Add each image for this round of exposures
                if is_primary:
                    primary_imgs.append(obs_info)
                else:
                    secondary_imgs.append(obs_info)

            # Now add the exposure to the list of images with a key corresponding to the start time
            self.primary_images[start_time] = primary_imgs
            self.secondary_images[start_time] = secondary_imgs

        except error.InvalidCommand as e:
            self.logger.warning("{} is already running a command.".format(cam.name))
            self._is_exposing = False
        except Exception as e:
            self.logger.warning("Problem with taking exposure: {}".format(e))
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

##################################################################################################
# Private Methods
##################################################################################################

    def _create_exposures(self, obs_config):
        self.logger.debug("Creating exposures")
        primary_exptime = obs_config.get('primary_exptime', 120) * u.s
        primary_filter = obs_config.get('primary_filter', None)
        primary_nexp = obs_config.get('primary_nexp', 1)
        analyze = obs_config.get('primary_analyze', False)

        primary_exposures = [Exposure(
            exptime=primary_exptime,
            filter=primary_filter,
            analyze=analyze,
        ) for x in range(primary_nexp)]
        self.logger.debug("Primary exposures: {}".format(primary_exposures))

        # secondary_exptime (assumes units of seconds, defaults to 120 seconds)
        secondary_exptime = obs_config.get('secondary_exptime', 120) * u.s
        secondary_nexp = obs_config.get('secondary_nexp', primary_nexp)
        secondary_filter = obs_config.get('secondary_filter', None)

        secondary_exposures = [Exposure(
            exptime=secondary_exptime,
            filter=secondary_filter,
            analyze=analyze,
        ) for x in range(secondary_nexp)]
        self.logger.debug("Secondary exposures: {}".format(secondary_exposures))

        return {'primary': primary_exposures, 'secondary': secondary_exposures}
