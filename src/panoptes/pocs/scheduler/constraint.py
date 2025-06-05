from contextlib import suppress

from astropy import units as u
from astropy.time import Time
from dateutil.parser import parse as parse_date
from panoptes.utils import error, horizon as horizon_utils
from panoptes.utils.utils import get_quantity_value

from panoptes.pocs.base import PanBase


class BaseConstraint(PanBase):

    def __init__(self, weight=1.0, default_score=0.0, *args, **kwargs):
        """ Base constraint

        Each constraint consists of a `get_score` method that is responsible
        for determining a score for a particular target and observer at a given
        time. The `score` is then multiplied by the `weight` of the constraint.

        Args:
            weight (float, optional): The weight of the observation, which will
                be multiplied by the score.
            default_score (float, optional): The starting score for observation.
        """
        super().__init__(*args, **kwargs)

        self.name = self.__class__.__name__

        weight = float(weight)
        assert isinstance(weight, float), \
            self.logger.error("Constraint weight must be a float greater than 0.0")
        assert weight >= 0.0, \
            self.logger.error("Constraint weight must be a float greater than 0.0")

        self.weight = weight
        self._score = default_score

    def get_score(self, time, observer, target, **kwargs):
        raise NotImplementedError

    def __str__(self):
        return self.name


class Altitude(BaseConstraint):
    """ Implements altitude constraints for a horizon """

    def __init__(self, horizon=None, obstructions=None, *args, **kwargs):
        """Create an Altitude constraint from a valid `Horizon`. """
        super().__init__(*args, **kwargs)

        if isinstance(horizon, horizon_utils.Horizon):
            self.horizon_line = horizon.horizon_line
        elif horizon is None or isinstance(horizon, (int, float, u.Quantity)):
            obstruction_list = obstructions
            default_horizon = horizon

            if obstructions is None:
                obstruction_list = self.get_config('location.obstructions', default=[])

            if default_horizon is None:
                default_horizon = self.get_config('location.horizon', default=30 * u.degree)

            horizon_obj = horizon_utils.Horizon(
                obstructions=obstruction_list,
                default_horizon=get_quantity_value(default_horizon)
            )

            self.horizon_line = horizon_obj.horizon_line

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        target = observation.field

        # Note we just get nearest integer
        target_az = observer.altaz(time, target=target).az.degree
        target_alt = observer.altaz(time, target=target).alt.degree

        # Determine if the target altitude is above or below the determined
        # minimum elevation for that azimuth
        min_alt = self.horizon_line[int(target_az)]

        with suppress(AttributeError):
            min_alt = get_quantity_value(min_alt, u.degree)

        self.logger.debug(f'Target coords: {target_az=:.02f} {target_alt=:.02f}')
        if target_alt < min_alt:
            self.logger.debug(f"Below minimum altitude: {target_alt:.02f} < {min_alt:.02f}")
            veto = True
        else:
            score = 1
        return veto, score * self.weight


class Duration(BaseConstraint):

    @u.quantity_input(horizon=u.degree)
    def __init__(self, horizon=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if horizon is None:
            horizon = self.get_config('location.horizon', default=30 * u.degree)

        self.horizon = horizon

    def get_score(self, time, observer, observation, **kwargs):
        score = self._score
        target = observation.field
        veto = not observer.target_is_up(time, target, horizon=self.horizon)

        end_of_night = observer.tonight(
            time=time,
            horizon=self.get_config(
                'location.observe_horizon',
                default=-18 * u.degree
            )
        )[1]

        if not veto:
            # Get the next meridian flip
            target_meridian = observer.target_meridian_transit_time(time, target, which='next')

            # If it flips before end_of_night it hasn't flipped yet so
            # use the meridian time as the end time
            if target_meridian < end_of_night:

                # If target can't meet minimum duration before flip, veto
                if time + observation.minimum_duration > target_meridian:
                    self.logger.debug("\t\tObservation minimum can't be met before meridian flip")
                    veto = True

            # else:
            # Get the next set time
            target_end_time = observer.target_set_time(
                time, target,
                which='next',
                horizon=self.horizon
            )

            # If end_of_night happens before target sets, use end_of_night
            if target_end_time > end_of_night:
                self.logger.debug("\t\tTarget sets past end_of_night, using end_of_night")
                target_end_time = end_of_night

            # Total seconds is score
            score = (target_end_time - time).sec
            if score < get_quantity_value(observation.minimum_duration, u.second):
                veto = True

            # Normalize the score based on total possible number of seconds
            score = score / (end_of_night - time).sec

        return veto, score * self.weight

    def __str__(self):
        return f"Duration above {self.horizon}"


class MoonAvoidance(BaseConstraint):

    def __init__(self, separation=15 * u.degree, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(separation, u.Unit):
            separation *= u.degree
        self.separation = separation

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        try:
            moon = kwargs['moon']
        except KeyError:
            raise error.PanError(f'Moon must be set for MoonAvoidance constraint')

        moon_sep = get_quantity_value(moon.separation(observation.field.coord, origin_mismatch='ignore'))

        # Check we are a certain number of degrees from moon.
        if moon_sep < get_quantity_value(self.separation):
            self.logger.debug(f'Moon separation: {moon_sep:.02f} < {self.separation:.02f}')
            veto = True
        else:
            score = (moon_sep / 180)

        return veto, score * self.weight

    def __str__(self):
        return f'Moon Avoidance ({self.separation})'


class AlreadyVisited(BaseConstraint):
    """ Simple Already Visited Constraint

    A simple already visited constraint that determines if the given `observation`
    has already been visited before. If given `observation` has already been
    visited then it will not be considered for a call to become the `current observation`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        observed_list = kwargs.get('observed_list')

        observed_field_list = [obs.field for obs in observed_list.values()]

        if observation.field in observed_field_list:
            veto = True

        return veto, score * self.weight


class TimeWindow(BaseConstraint):

    def __init__(self, start_time: str | Time, end_time: str | Time, *args, **kwargs):
        """Constraint that changes the weight of the field during a given time window.

        This constraint will set the score to 1 if the current time is within the
        specified time window (between `start_time` and `end_time`). The weight of
        the constraint is set to a high value by default (100.0) to ensure it is
        prioritized over other constraints. If the current time is outside the window,
        the score remains at its default value (0.0) and the weight is unchanged.

        This allows for prioritization of observations during specific times, such as
        when a target is in transit or at a specific altitude.

        Args:
            start_time (str|Time): Start time of the observation window. If passed as a string,
                it should be in a format that can be parsed by `dateutil.parser.parse`.
            end_time (str|Time): End time of the observation window. If passed as a string,
                it should be in a format that can be parsed by `dateutil.parser.parse`.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """

        # Set a high weight by default to ensure this constraint is prioritized.
        kwargs.setdefault('weight', 100.0)

        super().__init__(*args, **kwargs)
        self.logger.debug("Creating TimeWindow constraint")
        try:
            if isinstance(start_time, str):
                start_time = Time(parse_date(start_time))
            if isinstance(end_time, str):
                end_time = Time(parse_date(end_time))
        except ValueError:
            raise error.PanError(f"Invalid time format for start_time or end_time: {start_time}, {end_time}")

        # Make sure end time is after start time
        if end_time <= start_time:
            raise error.PanError(f"End time {end_time} must be after start time {start_time}")

        self.start_time = start_time
        self.end_time = end_time
        self.logger.debug(f"TimeWindow constraint: {self.start_time} to {self.end_time}")

    def get_score(self, time, observer, observation, **kwargs):
        score = self._score
        veto = False

        # If we are within the time window, set the score to one.
        if self.start_time <= time <= self.end_time:
            score = 1

        return veto, score * self.weight

    def __str__(self):
        return f"TimeWindow"

    def __repr__(self):
        return f"TimeWindow(start_time={self.start_time.iso}, end_time={self.end_time.iso})"
