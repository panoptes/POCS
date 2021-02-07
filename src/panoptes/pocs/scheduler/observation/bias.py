import os
from astropy import units as u

from panoptes.utils.config.client import get_config

from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation


class BiasObservation(Observation):

    def __init__(self, position, min_nexp=None, exp_set_size=None):

        # Use get_config to get config before initialising the class
        if min_nexp is None:
            min_nexp = get_config("calibs.bias.min_nexp", default=10)
        if exp_set_size is None:
            exp_set_size = get_config("calibs.bias.exp_set_size", default=min_nexp)

        # Create a bias field
        field = Field('Bias', position=position)
        super().__init__(field=field, exptime=0 * u.second, min_nexp=min_nexp,
                         exp_set_size=exp_set_size, dark=True)

        # Specify directory root for file storage
        self._directory = os.path.join(self._image_dir, 'bias')

    def __str__(self):
        return f"BiasObservation"
