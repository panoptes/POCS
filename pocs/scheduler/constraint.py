from astropy import units as u

from .. import PanBase


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
        super(Altitude, self).__init__(*args, **kwargs)

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
        super(Duration, self).__init__(*args, **kwargs)
        self.horizon = horizon

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        target = observation.field

        veto = not observer.target_is_up(time, target, horizon=self.horizon)

        if 'sunrise' in kwargs:
            sunrise = kwargs['sunrise']
        else:
            sunrise = observer.tonight(time=time, horizon=self.horizon)[1]

        if not veto:
            # Get the next meridian flip
            target_meridian = observer.target_meridian_transit_time(
                time, target,
                which='next')

            # If it flips before sunrise it hasn't flipped yet so
            # use the meridian time as the end time
            if target_meridian < sunrise:
                self.logger.debug("Target passes meridian before sunrise, using meridian")
                target_end_time = target_meridian
            else:
                # Get the next set time
                target_end_time = observer.target_set_time(
                    time, target,
                    which='next',
                    horizon=self.horizon)

                # If sunrise happens before target sets, use sunrise
                if target_end_time > sunrise:
                    self.logger.debug("Target sets past sunrise, using sunrise")
                    target_end_time = sunrise

            # Total seconds is score
            score = (target_end_time - time).sec
            if score < observation.minimum_duration.value:
                veto = True

            # Normalize the score based on total possible number of seconds
            score = score / (sunrise - time).sec

        return veto, score * self.weight

    def __str__(self):
        return "Duration above {}".format(self.horizon)
