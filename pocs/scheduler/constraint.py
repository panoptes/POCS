from astropy import units as u

from collections import OrderedDict

from pocs import PanBase


class BaseConstraint(PanBase):

    def __init__(self, weight=1.0, default_score=0.0, *args, **kwargs):
        """ Base constraint

        Each constraint consists of a `get_score` method that is responsible
        for determining a score for a particular target and observer at a given
        time. The `score` is then multiplied by the `weight` of the constraint.

        Args:
            weight (float, optional): The weight of the observation, which will
                be multipled by the score
            default_score (float, optional): The starting score for observation
            *args (TYPE): Description
            **kwargs (TYPE): Description
        """
        super(BaseConstraint, self).__init__(*args, **kwargs)

        assert isinstance(weight, float), \
            self.logger.error("Constraint weight must be a float greater than 0.0")
        assert weight >= 0.0, \
            self.logger.error("Constraint weight must be a float greater than 0.0")

        self.weight = weight
        self._score = default_score

    def get_score(self, time, observer, target):
        raise NotImplementedError


class Altitude(BaseConstraint):

    """ Simple Altitude Constraint

    A simple altitude constraint that determines if the given `observation` is
    above a minimum altitude.

    Note:
        This functionality can also be accomplished more directly with the
        `Duration` constraint

    Attributes:
        minimum (u.degree): The minimum acceptable altitude at which to observe
    """
    @u.quantity_input(minimum=u.degree)
    def __init__(self, minimum, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.minimum = minimum

    def get_score(self, time, observer, observation, **kwargs):
        target = observation.field

        alt = observer.altaz(time, target=target).alt

        veto = False
        score = self._score

        if alt < self.minimum:
            veto = True

        if alt >= self.minimum:
            score = 1.0

        return veto, score * self.weight

    def __str__(self):
        return "Altitude {}".format(self.minimum)


class Duration(BaseConstraint):

    @u.quantity_input(horizon=u.degree)
    def __init__(self, horizon, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.horizon = horizon

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        target = observation.field

        veto = not observer.target_is_up(time, target, horizon=self.horizon)

        end_of_night = kwargs.get('end_of_night',
                                  observer.tonight(time=time, horizon=-18 * u.degree)[1])

        if not veto:
            # Get the next meridian flip
            target_meridian = observer.target_meridian_transit_time(
                time, target,
                which='next')

            # If it flips before end_of_night it hasn't flipped yet so
            # use the meridian time as the end time
            if target_meridian < end_of_night:

                # If target can't meet minimum duration before flip, veto
                if time + observation.minimum_duration > target_meridian:
                    self.logger.debug("Observation minimum can't be met before meridian flip")
                    veto = True

            # else:
            # Get the next set time
            target_end_time = observer.target_set_time(
                time, target,
                which='next',
                horizon=self.horizon)

            # If end_of_night happens before target sets, use end_of_night
            if target_end_time > end_of_night:
                self.logger.debug("Target sets past end_of_night, using end_of_night")
                target_end_time = end_of_night

            # Total seconds is score
            score = (target_end_time - time).sec
            if score < observation.minimum_duration.value:
                veto = True

            # Normalize the score based on total possible number of seconds
            score = score / (end_of_night - time).sec

        return veto, score * self.weight

    def __str__(self):
        return "Duration above {}".format(self.horizon)


class MoonAvoidance(BaseConstraint):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        try:
            moon = kwargs['moon']
        except KeyError:
            self.logger.error("Moon must be set")

        moon_sep = moon.separation(observation.field.coord).value

        # This would potentially be within image
        if moon_sep < 15:
            self.logger.debug("Moon separation: {}".format(moon_sep))
            veto = True
        else:
            score = (moon_sep / 180)

        return veto, score * self.weight

    def __str__(self):
        return "Moon Avoidance"

class AlreadyVisited(BaseConstraint):

    """ Simple Already Visited Constraint

    A simple already visited constraint that determines if the given `observation`
    has already been visited before.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        target = observation.field
        observed_list = kwargs.get('observed_list', observer.observed_list)

        if target in observed_list:
            veto = True

        return veto, score * self.weight

    def __str__(self):
        return "Already Visited"
