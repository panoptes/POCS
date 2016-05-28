import matplotlib as mpl
import os
mpl.use('Agg')
import numpy as np

from astropy import units as u
from astropy.coordinates import SkyCoord

from astroplan import FixedTarget

from matplotlib import cm
from matplotlib import pyplot as plt

from ..utils import current_time
from ..utils import images
from ..utils.config import load_config
from ..utils.error import *
from ..utils.logger import get_logger

from .observation import Observation

try:
    import seaborn
    seaborn.set()
except:
    matplotlib.use('Agg')
    plt.style.use('ggplot')


# ----------------------------------------------------------------------------
# Target Class
# ----------------------------------------------------------------------------


class Target(FixedTarget):

    """An object describing an astronomical target.

    An object representing a possible target which the scheduler is considering,
    also is the object which the scheduler will return when asked for a target
    to observe.
    """

    def __init__(self, target_config, cameras=None, messaging=None, **kwargs):
        """  A FixedTarget object that we want to gather data about.

        A `Target` represents not only the actual object in the night sky
        (via the `self.coord` astropy.SkyCoord attribute) but also the concept
        of a `visit`, which is a list of `Observation`s.

        """
        self.config = load_config()
        self.logger = get_logger(self)

        assert 'name' in target_config, self.logger.warning("Problem with Target, trying adding a name")
        # assert 'position' in target_config, self.logger.warning("Problem with Target, trying adding a position")
        assert isinstance(target_config['name'], str)

        name = target_config.get('name', 'XXX')

        sky_coord = self.create_skycoord(target_config)

        super(Target, self).__init__(name=name, coord=sky_coord, **kwargs)

        self.coord.equinox = target_config.get('equinox', '2000')
        self.coord.epoch = target_config.get('epoch', 2000.)
        self.priority = target_config.get('priority', 1.0)

        # proper motion (is tuple of dRA/dt dDec/dt)
        self.proper_motion = target_config.get('proper_motion', '0.0 0.0').split()

        self.start_time = current_time(flatten=True)
        self._target_dir = '{}/fields/{}/{}'.format(self.config['directories']['images'],
                                                    self.name.title().replace(' ', '').replace('-', ''),
                                                    self.start_time)
        self.logger.debug("Target Directory: {}".format(self._target_dir))

        # Each target as a `visit` that is a list of Observations
        self.logger.debug("Creating visits")

        self.visit = [Observation(od, cameras=cameras, target_dir=self._target_dir, visit_num=num, messaging=messaging)
                      for num, od in enumerate(target_config.get('visit', [{}]))]

        self.logger.debug("Visits: {}".format(len(self.visit)))
        self.visits = self.get_visit_iter()
        self.logger.debug("Visits set")

        self.current_visit = None
        self._visit_num = 0

        self.logger.debug("Adding initial offset information")
        self._guide_wcsinfo = {}
        self.offset_info = {}
        self._reference_image = None

        self._done_visiting = False

        self._dx = []
        self._dy = []
        self._num_col = 0
        self._num_row = 0

        # Plotting options
        self.logger.debug("Adding plotting options")
        self._max_row = 5
        self._max_col = 6
        self._drift_fig = None
        self._drift_axes = None
        self._box_width = 500
        self._stamp_width = 8

##################################################################################################
# Properties
##################################################################################################

    @property
    def guide_wcsinfo(self):
        return self._guide_wcsinfo

    @guide_wcsinfo.setter
    def guide_wcsinfo(self, wcs_info):
        self.logger.debug("Setting WCS information for guide image")

        if 'wcs_file' in wcs_info:
            self.logger.debug("Getting target center coordinates from WCS: {}".format(wcs_info['wcs_file']))
            center_coords = self._get_target_position(wcs_info['wcs_file'])
            wcs_info['target_center_xy'] = center_coords

        self._guide_wcsinfo = wcs_info

    @property
    def has_reference_image(self):
        return self._reference_image is not None

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
                    for cam_name, img_info in first_exp.images.items():
                        if img_info.get('primary', False):
                            self.logger.debug("Reference image: {}".format(img_info))

                            img_data = images.read_image_data(img_info['img_file'])
                            self._reference_image = images.crop_data(img_data, box_width=self._box_width)

                            break

            except Exception as e:
                self.logger.debug("Can't get reference exposure: {}".format(e))

        return self._reference_image

##################################################################################################
# Methods
##################################################################################################

    def status(self):
        _status = {
            'visit_num': self.visit_num,
        }

        if self.current_visit:
            _status['exp_num'] = self.current_visit.exp_num

        return _status

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
        self.logger.debug("Resetting current visit")

        self.logger.debug("Getting new visits iterator")
        for visit in self.get_visit_iter():
            self.logger.debug("Resetting exposures for visit {}".format(visit))
            visit.reset_exposures()

        self.visits = None
        self.visits = self.get_visit_iter()

        self._target_dir = '{}/{}/{}'.format(self.config['directories']['images'],
                                             self.name.title().replace(' ', ''),
                                             current_time().isot.replace('-', '').replace(':', '').split('.')[0])

        self._drift_fig, self._drift_axes = plt.subplots(
            nrows=self._max_row, ncols=self._max_col, sharex=True, sharey=True)

        self.current_visit = None
        self._reference_image = None

        self._done_visiting = False
        self._guide_wcsinfo = {}
        self._dx = []
        self._dy = []
        self._num_col = 0
        self._num_row = 0

    def get_image_offset(self, exposure, with_plot=False):
        """ Gets the offset information for the `exposure` """
        d1 = self.reference_image

        self.logger.debug("Getting image offset from data: {}".format(type(d1)))
        # Make sure we have a reference image
        if d1 is not None:

            d2 = None
            for cam_name, img_info in exposure.images.items():
                if img_info.get('primary', False):
                    self.logger.debug("Cropping image data: {}".format(img_info['img_file']))
                    img_data = images.read_image_data(img_info['img_file'])
                    d2 = images.crop_data(img_data, box_width=self._box_width)
                    break

            if d2 is not None:
                # Do the actual phase translation
                info = self.guide_wcsinfo
                info['delta_time'] = exposure.exptime + (5.0 * u.second)
                self.offset_info = images.measure_offset(d1, d2, info=info)
                self.logger.debug("Updated offset info: {}".format(self.offset_info))

                if with_plot:
                    try:
                        self._update_plot(img_data)
                    except Exception as e:
                        self.logger.warning("Can't generate drift plot: {}".format(e))

            # Bookkeeping for graph
            self.logger.debug("Bookkeeping")
            self._num_col = self._num_col + 1
            if self._num_col == self._max_col:
                self._num_row = self._num_row + 1
                self._num_col = 0
                if self._num_row == self._max_row:
                    plt.close(self._drift_fig)

        self.logger.debug("Offset info: {}".format(self.offset_info))
        return self.offset_info

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

    def create_skycoord(self, target_config={}):
        """ Create a SkyCoord from the config.

        `config` can either pass a `position` keyword that contains the target's
        position as an HMS and DMS string, or the `ra` and `dec` keywords which
        are in degree units. If neither keyword is given an attempt is made to
        look up the target by `name`.

        Parameters
        ----------
        config : {dict}, optional
            Config entry containing either `position` or `ra` and `dec` (the default is {}, which returns None)

        Returns
        -------
        SkyCoord
            A SkyCoord corresponding to the desired target.
        """

        sky_coord = None

        try:
            frame = target_config.get('frame', 'icrs')
            if 'position' in target_config:
                self.logger.debug("Creating set of coordinates using position")
                sky_coord = SkyCoord(target_config['position'], frame=frame)

            elif 'ra' in target_config and 'dec' in target_config:
                self.logger.debug("Creating set of coordinates using RA/Dec")
                sky_coord = SkyCoord(target_config['ra'], target_config['dec'], frame=frame, unit='deg')
        except:
            self.logger.debug(
                "Create failed. Trying to look up coordinates for {}...".format(target_config.get('name')))
            sky_coord = SkyCoord.from_name(target_config.get('name'))
            if sky_coord is None:
                self.logger.warning("No position and can't look up coordinates")

        return sky_coord


##################################################################################################
# Private Methods
##################################################################################################

    def _init_plot(self):
        if self._drift_fig is None or self._drift_axes is None:
            self._drift_fig, self._drift_axes = plt.subplots(
                nrows=self._max_row, ncols=self._max_col, sharex=True, sharey=True)

            self._drift_fig.suptitle(
                '{} {}'.format(self.name, current_time().iso), fontsize=12, fontweight='bold', y=0.99)
            self._drift_fig.subplots_adjust(wspace=0.1, hspace=0.28, top=0.92)

    def _update_plot(self, img_data):
        self._init_plot()

        # Add to plot
        self.logger.debug("Adding axis for graph")
        ax = self._drift_axes[self._num_row][self._num_col]

        center_half = int(self._box_width / 2)
        box_center = self.guide_wcsinfo.get('target_center_xy', (center_half, center_half))
        center_d2 = images.crop_data(img_data, box_width=self._stamp_width, center=box_center)

        self.logger.debug("Center data: {}".format(center_d2.shape))

        ax.imshow(center_d2, origin='lower', cmap=cm.Blues_r)
        ax.set_title('{} UT'.format(current_time().isot.split('T')[1].split('.')[0]), fontsize=9)
        ax.tick_params(labelsize=9)
        ax.set_xticks(np.arange(1.5, self._stamp_width, step=2.0))
        ax.set_yticks(np.arange(1.5, self._stamp_width, step=2.0))
        ax.set_xlim(0, self._stamp_width)
        ax.set_ylim(0, self._stamp_width)

        self._save_fig()

    def _save_fig(self):
        self.logger.debug("Saving drift plot")

        if not os.path.exists(self._target_dir):
            try:
                os.mkdir(self._target_dir)
            except OSError as e:
                self.logger.warning("Can't make directory for target: {}".format(e))

        self._drift_fig_fn = '{}/drift.png'.format(self._target_dir)

        self._drift_fig.savefig(self._drift_fig_fn)

        link_fn = '/var/panoptes/images/drift.png'
        if os.path.lexists(link_fn):
            os.unlink(link_fn)

        os.symlink(self._drift_fig_fn, link_fn)

    def _get_exp_image(self, img_num):
        return list(self.images.values())[img_num]

    def _get_target_position(self, wcs_file):
        """ Get the x, y coordinates for the solved WCS info for this target """
        assert os.path.exists(wcs_file), self.logger.warning("No WCS info for target")

        self.logger.debug("About to get center")
        coords = images.get_target_position(self.coord, wcs_file)
        self.logger.debug("Center coordinates for target: {}".format(coords))
        return coords
