"""Compound observation that cycles through a set of exposure times."""

import numpy as np
from astropy import units as u
from panoptes.utils.utils import get_quantity_value, listify

from panoptes.pocs.scheduler.observation.base import Observation as BaseObservation


class Observation(BaseObservation):
    """An observation that consists of different combinations of exptimes."""

    def __init__(self, *args, **kwargs):
        """Accept a list of exptimes.

        Note: CompoundObservation requires an explicit exptime parameter (or list of exptimes).
        Unlike the base Observation class, it cannot use the camera config default because
        it needs a sequence of exposure times to cycle through.
        """
        # Get exptime from kwargs, raise clear error if not provided
        if "exptime" not in kwargs:
            raise ValueError(
                "CompoundObservation requires an 'exptime' parameter. "
                "Provide a single value or a list of exposure times to cycle through."
            )

        # Save all the exptimes.
        self._exptimes = listify(kwargs["exptime"])

        # Use the first exposure time to set up observation.
        kwargs["exptime"] = self._exptimes[0]
        super().__init__(*args, **kwargs)

        self._min_duration = np.sum(self._exptimes)
        self._set_duration = np.sum(
            [self._exptimes[i % len(self._exptimes)] for i in range(self.exp_set_size)]
        )

        self.is_compound = True

    @property
    def exptime(self):
        """Return current exposure time as a u.Quantity."""
        current_exptime_index = self.current_exp_num % len(self._exptimes)
        exptime = self._exptimes[current_exptime_index]
        return get_quantity_value(exptime, u.second) * u.second

    @property
    def exptimes(self):
        """List[Quantity | float]: The sequence of exposure times to cycle through."""
        return self._exptimes

    def __str__(self):
        return (
            f"{self.field}: exptime={self.exptime} "
            f"exptime_set={self._exptimes!r} "
            f"in blocks of {self.exp_set_size}, "
            f"minimum {self.min_nexp}, "
            f"priority {self.priority:.0f}"
        )

    @classmethod
    def from_dict(cls, *args, **kwargs):
        """Creates an `Observation` object from config dict."""
        return super().from_dict(observation_class=cls, *args, **kwargs)
