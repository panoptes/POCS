import os
from astropy import units as u

from panoptes.utils.utils import get_quantity_value
from panoptes.utils.utils import listify

from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation


class DarkObservation(Observation):

    def __init__(self, position, exptimes=None):
        """
        Args:
            position (str): Center of field, can be anything accepted by
                `~astropy.coordinates.SkyCoord`.
            exptimes (optional): The list of exposure times. If None (default), get from config.
        """
        # Set the exposure times
        if exptimes is not None:
            exptimes = listify(exptimes)
        else:
            exptimes = self.get_config("calibs.dark.exposure_times")
        self._exptimes = exptimes

        # Create the observation
        min_nexp = len(self._exptimes)
        exp_set_size = min_nexp
        field = Field('Dark', position=position)
        super().__init__(field=field, min_nexp=min_nexp, exp_set_size=exp_set_size, dark=True)

        # Specify directory root for file storage
        self._directory = os.path.join(self._image_dir, 'dark')

    def __str__(self):
        return f"DarkObservation"

    @property
    def exptime(self):
        """ Return current exposure time as a u.Quantity. """
        exptime = self._exptimes[self.current_exp_num]
        return get_quantity_value(exptime, u.second) * u.second
