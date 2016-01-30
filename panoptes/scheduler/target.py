import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

from astroplan import FixedTarget

import numpy as np
import seaborn
from matplotlib import pyplot as plt
from matplotlib import cm as cm

from ..utils.error import *
from ..utils.logger import get_logger
from ..utils.config import load_config
from ..utils import images

from .observation import Observation

# ----------------------------------------------------------------------------
# Target Class
# ----------------------------------------------------------------------------


class Target(FixedTarget):

    """An object describing an astronomical target.

    An object representing a possible target which the scheduler is considering,
    also is the object which the scheduler will return when asked for a target
    to observe.
    """

    def __init__(self, target_config, cameras=None, **kwargs):
        """  A FixedTarget object that we want to gather data about.

        A `Target` represents not only the actual object in the night sky
        (via the `self.coord` astropy.SkyCoord attribute) but also the concept
        of a `visit`, which is a list of `Observation`s.

        """
        self.config = load_config()
        self.logger = get_logger(self)

        assert 'name' in target_config, self.logger.warning("Problem with Target, trying adding a name")
        assert 'position' in target_config, self.logger.warning("Problem with Target, trying adding a position")
        assert isinstance(target_config['name'], str)

        name = target_config.get('name', None)
        sky_coord = None

        try:
            self.logger.debug("Looking up coordinates for {}...".format(name))
            sky_coord = SkyCoord.from_name(name)
        except:
            self.logger.debug("Looking up coordinates failed, using dict")
            sky_coord = SkyCoord(target_config['position'], frame=target_config.get('frame', 'icrs'))

        super().__init__(name=name, coord=sky_coord, **kwargs)

        self.coord.equinox = target_config.get('equinox', '2000')
        self.coord.epoch = target_config.get('epoch', 2000.)
        self.priority = target_config.get('priority', 1.0)

        # proper motion (is tuple of dRA/dt dDec/dt)
        proper_motion = target_config.get('proper_motion', '0.0 0.0').split()
        self.proper_motion = (proper_motion[0], proper_motion[1])

        # Each target as a `visit` that is a list of Observations
        self.logger.debug("Creating visits")
        self.visit = [Observation(od, cameras=cameras) for od in target_config.get('visit', [{}])]
        self.logger.debug("Visits: {}".format(self.visit))
        self.visits = self.get_visit_iter()
        self.current_visit = None
        self._done_visiting = False
        self._visit_num = 0
        # self.reset_visits()

        self._reference_image = None
        self._offset_info = {}
        self._previous_center = None

        self._drift_fig = plt.figure()
        self._max_cols = 6
        self._max_rows = len(self.visit) / self._max_cols

        self._guide_wcsinfo = {}

        self._target_dir = Time.now().isot.replace('-', '').replace(':', '').split('.')[0]

        self._dx = []
        self._dy = []
        self._num_col = 0
        self._num_row = 0

##################################################################################################
# Properties
##################################################################################################

    @property
    def target_dir(self):
        return self._target_dir

    @property
    def visit_num(self):
        return self._visit_num

    @property
    def done_visiting(self):
        """ Bool indicating whether or not any observations are left """
        self.logger.debug("Done visiting: {}".format(self._done_visiting))

        return self._done_visiting

    @property
    def reference_image(self):
        """ Reference image for the target """
        if self._reference_image is None:
            try:
                first_visit = self.visit[0]
                first_exp = first_visit.exposures[0]
                self.logger.debug("First visit: {}".format(first_visit))

                if first_exp:
                    self.logger.debug("First visit images: {}".format(first_exp.images))
                    self._reference_image = list(first_exp.images.values())[0]
            except Exception as e:
                self.logger.debug("Can't get reference exposure: {}".format(e))

        return self._reference_image

##################################################################################################
# Methods
##################################################################################################

    def get_visit_iter(self):
        """ Yields the next visit """

        for num, visit in enumerate(self.visit):
            self.logger.debug("Getting next visit ({})".format(visit))
            self._visit_num = num

            self.current_visit = visit
            if num == len(self.visit) - 1:
                self.logger.debug("Setting done visiting: {} {}".format(num, len(self.visit) - 1))
                self._done_visiting = True

            yield visit

    def get_visit(self):
        """ Get the visit from the iterator.

        Checks if the `current_visit` is complete and if so gets a new visit.
        Also handles getting first visit properly.
        """

        visit = self.current_visit

        if visit is None or visit.complete:
            visit = next(self.visits)
            self._visit_num = self._visit_num + 1
            self.current_visit = visit

        return visit

    def reset_visits(self):
        """ Resets the exposures iterator """
        for visit in self.get_visit_iter():
            self.logger.debug("Resetting exposures for visit {}".format(visit))
            visit.reset_exposures()

        self.logger.debug("Getting new visits iterator")

        self.logger.debug("Resetting current visit")
        self.current_visit = None
        self._done_visiting = False

    def get_image_offset(self, exposure):
        """ Gets the offset information for the `exposure` """
        d1 = self._previous_center

        self.logger.debug("Getting image offset")
        # Make sure we have a reference image
        if d1 is not None:

            last_image = exposure.images[list(exposure.images)[-1]]

            self.logger.debug("Cropping image data: {}".format(last_image['img_file']))
            d2 = images.crop_data(images.read_image_data(last_image['img_file']), box_width=500)

            if d1 is None or d2 is None:
                raise error.PanError("Can't get image data")

            # Do the actual phase translation
            self._offset_info = images.measure_offset(d1, d2, self._guide_wcsinfo)
            self.logger.debug("Updated offset info")

            # Update to previous
            self._previous_center = d2

            # Get deltas
            delta = images.get_ra_dec_deltas(
                self._offset_info['delta_ra'],
                self._offset_info['delta_dec'],
                rotation=float(self._guide_wcsinfo['rotation']),
                pixel_scale=float(self._guide_wcsinfo['pixel_scale']),
            )
            self._dy.append(delta[0].value)
            self._dx.append(delta[1].value)

            # Add to plot
            ax = fig.subplot2grid((self._max_row, self._max_col), (self._num_row, self._num_col))
            ax.imshow(d2, origin='lower', cmap=cm.Blues_r)

            ax.set_title(img.split('/')[-1].replace('.cr2', ''))

            self._drift_fig.savefig('/var/panoptes/images/drift.png')

            # Bookkeeping for graph
            self._num_col = self._num_col + 1
            if self._num_col == self._max_col:
                self._num_row = self._num_row + 1
                self._num_col = 0

        self.logger.debug("Offset info: {}".format(self._offset_info))
        return self._offset_info

    def estimate_visit_duration(self, overhead=0 * u.s):
        """Method to estimate the duration of a visit to the target.

        A quick and dirty estimation of the time it takes to execute the
        visit.  Does not currently account for overheads such as readout time,
        slew time, or download time.

        This function just sums over the time estimates of the observations
        which make up the visit.

        Args:
            overhead (astropy.units.Quantity): The overhead time for the visit in
            units which are reducible to seconds.  This is the overhead which occurs
            for each observation.

        Returns:
            astropy.units.Quantity: The duration (with units of seconds).
        """
        duration = 0 * u.s
        for obs in self.visit:
            duration += obs.estimate_duration() + overhead
        self.logger.debug('Visit duration estimated as {}'.format(duration))
        return duration

##################################################################################################
# Private Methods
##################################################################################################

    def _get_exp_image(self, img_num):
        return list(self.images.values())[img_num]
